# -*- coding: utf-8 -*-

import logging
import multiprocessing
import os
import signal
import time
import json
import socket

import memcache
import yaml

from polaris_common import topology, sharedmem
from polaris_health import Error, config, prober, tracker
import polaris_health.util.log

__all__ = [ 'Guardian' ]

LOG = logging.getLogger(__name__)
LOG.addHandler(logging.NullHandler())

# timeout on control socket so we don't eat CPU in the control loop
# also affects how often Guardian healthcheck is ran
CONTROL_SOCKET_TIMEOUT = 0.5
# control socket recv() buffer size 
CONTROL_SOCKET_RECV_BUFF_SIZE = 256

# how often in seconds a heartbeat is written, heartbeat TTL is set to + 4
HEARTBEAT_INTERVAL = 1

# maximum number of times to .terminate() an alive process
MAX_TERMINATE_ATTEMPTS = 5
# delay between calling .terminate()
TERMINATE_ATTEMPT_DELAY = 0.1


class Guardian:

    """Polaris Guardian

    Loads configuration, sets up logging, starts other processes.
    Starts and periodically healthchecks other processes, if a child processes 
    dies shutdowns the applicaton.    
    Listens for control commands on UNIX socket.
    """

    def __init__(self):
        self._procs_started = None
        self._control_socket = None

        # multiprocessing.Process() objects of the child processes spawned
        self._processes = []

        # shared memory client
        self._sm = sharedmem.MemcacheClient(
            [config.BASE['SHARED_MEM_HOSTNAME']],
            socket_timeout=config.BASE['SHARED_MEM_SOCKET_TIMEOUT'],
            server_max_value_length=config.BASE['SHARED_MEM_SERVER_MAX_VALUE_LENGTH'])

    @staticmethod
    def load_configuration():        
        """Load configuration from files"""
        LOG.debug('loading Polaris health configuration')

        ### set config.BASE['INSTALL_PREFIX'] from POLARIS_INSTALL_PREFIX env
        try:
                config.BASE['INSTALL_PREFIX'] = \
                    os.environ['POLARIS_INSTALL_PREFIX']
        except KeyError:
            log_msg = 'POLARIS_INSTALL_PREFIX env is not set'
            LOG.error(log_msg)
            raise Error(log_msg)

        ### optionally load BASE configuration ###
        base_config_file = os.path.join(
            config.BASE['INSTALL_PREFIX'], 'etc', 'polaris-health.yaml')
        if os.path.isfile(base_config_file):
            with open(base_config_file) as fp:
                base_config = yaml.load(fp)

            if base_config:
                # validate and set values
                for k in base_config:
                    if k not in config.BASE:
                        log_msg =('unknown configuration option "{}"'
                                   .format(k))
                        LOG.error(log_msg)
                        raise Error(log_msg)
                    else:
                        config.BASE[k] = base_config[k]

        # hard set file paths based on INSTALL_PREFIX
        config.BASE['PID_FILE'] = os.path.join(
            config.BASE['INSTALL_PREFIX'], 'run', 'polaris-health.pid')

        config.BASE['CONTROL_SOCKET_FILE'] = os.path.join(
            config.BASE['INSTALL_PREFIX'], 
            'run', 'polaris-health.controlsocket')

        ### load LB configuration ###
        lb_config_file = os.path.join(
            config.BASE['INSTALL_PREFIX'], 'etc', 'polaris-lb.yaml')
        if not os.path.isfile(lb_config_file):
            log_msg = '{} does not exist'.format(lb_config_file)
            LOG.error(log_msg)
            raise Error(log_msg)
        else:
            with open(lb_config_file) as fp:
                config.LB = yaml.load(fp)

        ### optionally load TOPOLOGY_MAP configuration ###
        topology_config_file = os.path.join(
            config.BASE['INSTALL_PREFIX'], 'etc', 'polaris-topology.yaml')
        if os.path.isfile(topology_config_file):
            with open(topology_config_file) as fp:
                topology_config = yaml.load(fp)

            if topology_config:
                config.TOPOLOGY_MAP = topology.config_to_map(topology_config)

    def start(self, debug=False):
        """Start Polaris health.

        polaris_health.config must be loaded prior to calling this.

        If debug is True logging level is set to DEBUG with logs 
        sent to stdout.
        """
        # setup logging
        if debug:
            polaris_health.util.log.setup_debug()    
        else:
            polaris_health.util.log.setup()

        LOG.info('starting Polaris health')

        # FIXME defining probe queues in __init__() causes Prober process
        # to fail with EOFError raised when attempting to .get() 
        # from the request queue

        # probe requests are put on this queue by Tracker
        # to be consumed by Prober processes
        self._prober_requests = multiprocessing.Queue()

        # processed probes are put on this queue by Prober processes to be
        # consumed by Tracker
        self._prober_responses = multiprocessing.Queue()

        # instantiate Tracker, this will also validate the configuration
        p = tracker.Tracker(prober_requests=self._prober_requests,
                            prober_responses=self._prober_responses)
        self._processes.append(p)

        # instantiate Probers
        for i in range(config.BASE['NUM_PROBERS']):
            p = prober.ProberProcess(prober_requests=self._prober_requests,
                                     prober_responses=self._prober_responses)
            self._processes.append(p)

        # initialize control socket
        self._init_control_socket()

        # write pid file
        self._write_pid_file()

        # start all the processes
        for p in self._processes:
            p.start()

        # If a code between child procs started/exited markers is expected to
        # throw an exception, all the child processes must be terminated
        # (call self._terminate_child_procs()) prior to exiting 
        # to avoid zombies

        ###########################
        # child processes started # 
        ###########################

        # note the total number of child processes started 
        self._procs_started = len(self._processes)

        # trap SIGTERM to self.sigterm_handler
        signal.signal(signal.SIGTERM, self._sigterm_handler)

        # run the control loop
        self._control_loop()

        # control loop returns when no processes are left running,
        # join() the processes
        for p in self._processes:
            p.join()

        ##########################
        # child processes exited #
        ##########################

        # clean up the control socket
        if self._control_socket:
            self._control_socket.close()
        self._delete_control_socket_file()

        # delete the pid file
        self._delete_pid_file()

        LOG.info('Polaris health finished execution')

    def _control_loop(self):
        """Accept and processes incoming connections on the control socket,
        verify that all the processes spawned by the Guardian are alive
        (terminate the app if one of the child processes dies),
        push heartbeat into the shared memory
        """
        # setting t_last so that "if t_now - t_last >= HEALTHCHECK_INTERVAL"
        # below evalutes to True on the first run and a heartbeat is written
        t_last = time.monotonic() - HEARTBEAT_INTERVAL - 1

        while True:
            ### process control connections ###
            try:
                conn, client_addr = self._control_socket.accept()
            # e.g. timeout
            except OSError:
                pass
            else:
                try:
                    self._process_control_connection(conn)
                except Exception as e:
                    log_msg = ('caught {} {} during control '
                               'connection processing'
                               .format(e.__class__.__name__, e))
                    LOG.warning(log_msg)
                               
            ### health check the child procs ###
            alive = 0
            for p in self._processes:
                if p.is_alive():
                    alive += 1

            # no processes are alive - exit the control loop
            if alive == 0:
                LOG.debug(
                    'no child processes are alive, exiting the control loop')
                return

            # one or more child proc(s) exited
            # terminate the remaining procs and and exit the loop
            if alive != self._procs_started:
                log_msg = ('processes started: {} processes alive: {}'
                           .format(self._procs_started, alive))
                LOG.error(log_msg)
                self._terminate_child_procs()
                return

            ### push heartbeat ###
            t_now = time.monotonic()
            if t_now - t_last >= HEARTBEAT_INTERVAL:
                obj = { 'timestamp': time.time() }
                val = self._sm.set(config.BASE['SHARED_MEM_HEARTBEAT_KEY'],
                                   json.dumps(obj), 
                                   HEARTBEAT_INTERVAL + 4)
                if val is not True:
                    log_msg = 'failed to write heartbeat to the shared memory'
                    LOG.warning(log_msg)

                t_last = t_now

    def _process_control_connection(self, conn):
        """Process a connection on the control socket.

        Receive and action a command.
        """
        data = conn.recv(CONTROL_SOCKET_RECV_BUFF_SIZE)
        if data:
            cmd = data.decode(errors='ignore')
            LOG.debug('received "{}" command'.format(cmd))

            if cmd == 'ping':
                conn.sendall('pong'.encode())
            elif cmd == 'stop':
                conn.sendall('ok'.encode())
                self._terminate_child_procs()
            else:
                LOG.warning('unknown control socket command received "{}"'
                            .format(cmd))

        conn.close()

    def _terminate_child_procs(self):
        """Terminate all the child procs.

        It has been observed that sometimes a process does not exit
        on .terminate(), we attempt to .terminate() it several times.
        """
        LOG.info('terminating {} processes...'.format(len(self._processes)))
 
        i = 0
        while i < MAX_TERMINATE_ATTEMPTS:
            i += 1

            # call .terminate() on alive processes, this sends SIGTERM
            for p in self._processes:
                if p.is_alive():
                    p.terminate()

            # give the processes some time to terminate
            time.sleep(TERMINATE_ATTEMPT_DELAY)

            # if we still have processes running, 
            # run the termination loop again 
            for p in self._processes:
                if p.is_alive():
                    LOG.warning('process {} is still running after ' 
                                'terminate() attempt {}'.format(p, i))
                    break
            # no processes are alive, exit out
            else:
                return

        # if we got here, some processes may still be alive, SIGKILL them
        LOG.error('Some processes may still be alive after all '
                  'termination attempts, SIGKILL-ing those')
        for p in self._processes:
            if p.is_alive():
                try:
                    os.kill(p.pid, signal.SIGKILL)
                except OSError:
                    pass

    def _write_pid_file(self):
        """Create file containing the PID of the Guardian process"""
        try:
            with open(config.BASE['PID_FILE'], 'w') as fh:
                fh.write(str(os.getpid()))
        except OSError as e:
            log_msg = ('unable to write the pid file {} - {} {}'
                       .format(config.BASE['PID_FILE'],
                               e.__class__.__name__, e))
            LOG.error(log_msg)
            raise Error(log_msg)

    def _delete_pid_file(self):
        """Delete Guardian process PID file"""
        try:
            os.remove(config.BASE['PID_FILE'])
        except OSError as e:
            log_msg = ('unable to delete pid file {} - {} {}'
                       .format(config.BASE['PID_FILE'], 
                               e.__class__.__name__, e))
            LOG.error(log_msg)
            raise Error(log_msg)

    def _init_control_socket(self):
        """Initialize the control socket.

        self._control_socket is created and bound 
        to config.BASE['CONTROL_SOCKET_FILE']
        """
        # make sure the socket file does not exist
        self._delete_control_socket_file()

        self._control_socket = socket.socket(socket.AF_UNIX,
                                             socket.SOCK_STREAM)
        # set a timeout on the socket so we don't eat CPU in the control loop
        self._control_socket.settimeout(CONTROL_SOCKET_TIMEOUT)

        try:
            self._control_socket.bind(config.BASE['CONTROL_SOCKET_FILE'])
        except OSError as e:
            log_msg = ('unable to bind control socket {} - {} {}'
                       .format(config.BASE['CONTROL_SOCKET_FILE'], 
                               e.__class__.__name__, e))
            LOG.error(log_msg)
            raise Error(log_msg)

        # listen on the socket for incoming connections
        self._control_socket.listen(1)

    def _delete_control_socket_file(self):
        """Delete control socket file"""
        try:
            os.unlink(config.BASE['CONTROL_SOCKET_FILE'])
        except OSError as e:
            if os.path.exists(config.BASE['CONTROL_SOCKET_FILE']):
                log_msg = ('unable to delete control socket {} - {} {}'
                           .format(config.BASE['CONTROL_SOCKET_FILE'],
                                   e.__class__.__name__, e))
                LOG.error(log_msg)

    def _sigterm_handler(self, signo, stack_frame):
        LOG.info('received sig {}'.format(signo))
        self._terminate_child_procs()

