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

from polaris_common import topology
from polaris_health import Error, config, prober, tracker


__all__ = [ 'Runtime' ]

LOG = logging.getLogger(__name__)
LOG.addHandler(logging.NullHandler())

# timeout on control socket operations
CONTROL_SOCKET_TIMEOUT = 0.1

# how often in seconds to run the heartbeat loop
HEARTBEAT_LOOP_INTERVAL = 0.5
# how often in seconds to log heartbeat into shared mem
HEARTBEAT_LOG_INTERVAL = 10
# how long in seconds should a heartbeat live in shared mem
HEARTBEAT_TTL = 31

# maximum number of times to .terminate() an alive process
MAX_TERMINATE_ATTEMPTS = 5
# delay between calling .terminate()
TERMINATE_ATTEMPT_DELAY = 0.2


class Runtime:

    """Polaris runtime"""

    def __init__(self):
        # this holds multiprocessing.Process() objects
        # of the child processes spawned by the Runtime
        self._processes = []

        # shared memory client
        self._sm = memcache.Client([config.BASE['SHARED_MEM_HOSTNAME']])

        # probe requests are put on this queue by Tracker
        # to be consumed by Prober processes
        self._probe_request_queue = multiprocessing.Queue()

        # processed probes are put on this queue by Prober processes to be
        # consumed by Tracker
        self._probe_response_queue = multiprocessing.Queue()

    def start(self):
        """Start Polaris health"""
        LOG.info('starting Polaris health...')

        # load configuration from files
        LOG.debug('loading configuration')
        self._load_configuration()

        # instantiate the Tracker first, this will validate the configuration
        # and throw an exception if there is a problem with it,
        # while we're still single threaded
        p = tracker.Tracker(probe_request_queue=self._probe_request_queue,
                            probe_response_queue=self._probe_response_queue)
        self._processes.append(p)

        # instantiate Probers
        for i in range(config.BASE['NUM_PROBERS']):
            p = prober.Prober(probe_request_queue=self._probe_request_queue,
                              probe_response_queue=self._probe_response_queue)
            self._processes.append(p)

        # initialize control socket
        self._init_control_socket()

        # create pid file
        self._create_pid_file()

        # start all the processes
        for p in self._processes:
            p.start()

        # Avoid code that migth throw an exceptions between child procs
        # started/exited markers, if an exception must be included, 
        # the handling code must terminate all
        # the child processes(call self.stop()) prior to exiting

        ###########################
        # Child processes started # 
        ###########################

        # note the total number of child processes started 
        self._procs_started = len(self._processes)

        # trap SIGTERM to self.sigterm_handler
        signal.signal(signal.SIGTERM, self._sigterm_handler)

        # run the heartbeat loop
        self._heartbeat_loop()

        # heartbeat loop returns when no processes are left running,
        # join() the processes
        for p in self._processes:
            p.join()

        ##########################
        # Child processes exited #
        ##########################

        # delete pid file
        self._delete_pid_file()

        # delete control socket file
        self._delete_control_socket_file()

        LOG.info('Polaris health finished execution')

    def stop(self):
        """Terminate all processes spawned by the Runtime

        It has been observed that sometimes a process does not exit
        on .terminate(), we attempt to .terminate() it several times.
        """
        i = 0
        while i < MAX_TERMINATE_ATTEMPTS:
            i += 1

            # call .terminate() on alive processes, this sends SIGTERM
            for p in self._processes:
                if p.is_alive():
                    p.terminate()

            # give the processes some time to terminate
            time.sleep(TERMINATE_ATTEMPT_DELAY)

            # if we still have processes running, run the termination loop again 
            for p in self._processes:
                if p.is_alive():
                    LOG.warning('process {} is still running after .terminate() '
                                'attempt {}'.format(p, i))
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

    def _create_pid_file(self):
        """Create file containing the PID of the Runtime process"""
        self._pid_file = os.path.join(
            config.BASE['INSTALL_PREFIX'], 'run', 'polaris-health.pid')
        LOG.debug('writting {}'.format(pid_file))

        try:
            with open(pid_file, 'w') as fh:
                fh.write(str(os.getpid()))
        except OSError as e:
            log_msg = 'unable tocreate {} - {}'.format(self._pid_file, e)
            LOG.error(log_msg)
            raise Error(log_msg)

    def _delete_pid_file(self):
        """Delete Runtime process PID file"""
        LOG.debug('removing {}'.format(self._pid_file))
        try:
            os.remove(self._pid_file)
        except OSError as e:
            log_msg = 'unable to delete {} - {}'.format(self._pid_file, e)
            LOG.error(log_msg)
            raise Error(log_msg)

    def _init_control_socket(self):
        """Initialize control socket

        self._control_socket is created and bound to self._control_socket_file
        """
        LOG.debug('initializing control socket')

        self._control_socket_file = os.path.join(
            config.BASE['INSTALL_PREFIX'],
            'run', 
            'polaris-health.controlsocket')
        
        # make sure socket file does not exist
        self._delete_control_socket_file()

        self._control_socket = socket.socket(socket.AF_UNIX,
                                             socket.SOCK_STREAM)
        # set a small timeout
        self._control_socket.settimeout(CONTROL_SOCKET_TIMEOUT)

        try:
            sock.bind(self._control_socket_file)
        except OSError as e:
            log_msg = 'unable to bind control socket - {}'.format(e)
            LOG.error(log_msg)
            raise Error(log_msg)

    def _delete_control_socket_file(self):
        """Delete control socket file"""
        try:
            os.unlink(self._control_socket_file)
        except OSError:
            if os.path.exists(self._control_socket_file)
                log_msg = ('unable to delete {}'
                           .format(self._control_socket_file))
                LOG.error(log_msg)

    def _heartbeat_loop(self):
        """Periodically log various internal application stats
        to the shared memory.
        """
        # set last time so that "if t_now - t_last >= HEARTBEAT_LOG_INTERVAL"
        # below evalutes to True on the first run
        t_last = time.time() - HEARTBEAT_LOG_INTERVAL - 1
        while True:
            alive = 0
            # count alive processes 
            for p in self._processes:
                if p.is_alive():
                    alive += 1

            # no processes are alive - exit heartbeat loop
            if alive == 0:
                return

            t_now = time.time()
            if t_now - t_last >= HEARTBEAT_LOG_INTERVAL:
                # log heartbeat
                obj = { 
                    'timestamp': time.time(),
                    'child_procs_total': self._procs_started,
                    'child_procs_alive': alive,
                    'probe_req_queue_len': self._probe_request_queue.qsize(),
                    'probe_resp_queue_len': \
                        self._probe_response_queue.qsize(),    
                }
                
                # push to shared mem
                self._sm.set(config.BASE['SHARED_MEM_HEARTBEAT_KEY'],
                             json.dumps(obj), HEARTBEAT_TTL)
                LOG.debug('pushed a heartbeat to the shared memory')

                t_last = t_now

            time.sleep(HEARTBEAT_LOOP_INTERVAL)

    def _sigterm_handler(self, signo, stack_frame):
        LOG.info('received sig {}, terminating {} processes...'.format(
                 signo, len(self._processes)))
        self.stop()

    def _load_configuration(self):        
        """load configuration from the file system"""

        ### set config.BASE['INSTALL_PREFIX']
        try:
            config.BASE['INSTALL_PREFIX'] = \
                os.environ['POLARIS_INSTALL_PREFIX']
        except KeyError:
            log_msg = 'POLARIS_INSTALL_PREFIX env is not set'
            LOG.error(log_msg)
            raise Error(log_msg)

        ### load BASE configuration
        base_config_file = os.path.join(
            config.BASE['INSTALL_PREFIX'], 'etc', 'polaris-health.yaml')
        if os.path.isfile(base_config_file):
            with open(base_config_file) as fp:
                base_config = yaml.load(fp)

            if base_config:
                # validate and set values
                for k in base_config:
                    if k not in config.BASE:
                        raise Exception('unknown configuration option "{}"'
                                        .format(k))
                    else:
                        config.BASE[k] = base_config[k]

        ### load LB configuration
        lb_config_file = os.path.join(
            config.BASE['INSTALL_PREFIX'], 'etc', 'polaris-lb.yaml')
        if not os.path.isfile(lb_config_file):
            raise Exception('{} does not exist'.format(lb_config_file))
        else:
            with open(lb_config_file) as fp:
                config.LB = yaml.load(fp)

        ### load TOPOLOGY_MAP configuration
        topology_config_file = os.path.join(
            config.BASE['INSTALL_PREFIX'], 'etc', 'polaris-topology.yaml')
        if os.path.isfile(topology_config_file):
            with open(topology_config_file) as fp:
                topology_config = yaml.load(fp)

            if topology_config:
                config.TOPOLOGY_MAP = \
                    topology.config_to_map(topology_config)

