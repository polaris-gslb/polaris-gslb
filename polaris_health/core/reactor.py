# -*- coding: utf-8 -*-

import logging
import multiprocessing
import sys
import os
import signal
import time
import json

import memcache

from polaris_health import config
from .tracker import Tracker
from .prober import Prober

__all__ = [ 'Reactor' ]

LOG = logging.getLogger(__name__)
LOG.addHandler(logging.NullHandler())

# how often in seconds to run the heartbeat loop
HEARTBEAT_LOOP_INTERVAL = 0.5
# how often in seconds to log heartbeat into shared mem
HEARTBEAT_LOG_INTERVAL = 10
# how long in seconds should a heartbeat live in shared mem
HEARTBEAT_TTL = 31

# this holds multiprocessing.Process() objects
# of the child processes spawned by the Reactor
PROCESSES = []
# maximum number of times to .terminate() an alive process
MAX_TERMINATE_ATTEMPTS = 5
# delay between calling .terminate()
TERMINATE_ATTEMPT_DELAY = 0.2

def sig_handler(signo, stack_frame):
    """Terminate all processes spawned by the Reactor()

    It has been observed that sometimes a process does not exit
    on .terminate(), we attempt to .terminate() it several times.

    """
    LOG.info('received sig {}, terminating {} processes...'.format(
        signo, len(PROCESSES)))

    i = 0
    while i < MAX_TERMINATE_ATTEMPTS:
        i += 1

        # call .terminate() on alive processes, this sends SIGTERM
        for p in PROCESSES:
            if p.is_alive():
                p.terminate()

        # give the processes some time to terminate
        time.sleep(TERMINATE_ATTEMPT_DELAY)

        # if we still have processes running, run the termination loop again 
        for p in PROCESSES:
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
    for p in PROCESSES:
        if p.is_alive():
            try:
                os.kill(p.pid, signal.SIGKILL)
            except OSError:
                pass

class Reactor:

    """Main manager process"""

    def __init__(self):
        LOG.info('starting Polaris health...')

        global PROCESSES
    
        # probe requests are put on this queue by Tracker 
        # to be consumed by Prober processes 
        self._probe_request_queue = multiprocessing.Queue()

        # processed probes are put on this queue by Prober processes to be 
        # consumed by Tracker
        self._probe_response_queue = multiprocessing.Queue()

        # instantiate the Tracker first, this will validate the configuration
        # and throw an exception if there is a problem with it
        self._tracker = Tracker(
            probe_request_queue=self._probe_request_queue,
            probe_response_queue=self._probe_response_queue)
        PROCESSES.append(self._tracker)

        # instantiate Probers
        for i in range(config.BASE['NUM_PROBERS']):
            p = Prober(
                probe_request_queue=self._probe_request_queue,
                probe_response_queue=self._probe_response_queue)
            PROCESSES.append(p)

        # start all the processes
        for p in PROCESSES:
            p.start()

        # record the total number of child processes started 
        self._procs_total = len(PROCESSES)

        # shared memory client
        self._sm = memcache.Client(
            config.BASE['SHARED_MEM_HOSTNAME'])

        # trap the signal to terminate upon
        signal.signal(signal.SIGTERM, sig_handler)

        pid_file = os.path.join(
            config.BASE['INSTALL_PREFIX'], 'run', 'polaris-health.pid')

        # write pid file
        LOG.debug('writting {}'.format(pid_file))    
        with open(pid_file, 'w') as fh:
            fh.write(str(os.getpid()))

        # run the heartbeat loop
        self._heartbeat_loop()

        # heartbeat loop returns when no processes are left running,
        # join() the processes
        for p in PROCESSES:
            p.join()

        # remove the pid file
        LOG.debug('removing {}'.format(pid_file))
        os.remove(pid_file)

        LOG.info('Polaris health finished execution')

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
            for p in PROCESSES:
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
                    'child_procs_total': self._procs_total,
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

