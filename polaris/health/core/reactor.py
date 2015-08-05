# -*- coding: utf-8 -*-

import logging
import multiprocessing
import sys
import os
import signal
import time

import json
import memcache

import polaris.config
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

def sig_handler(signo, stack_frame):
    """Terminate all processes spawned by the Reactor()"""

    LOG.info('received sig {}, terminating {} processes...'.format(
        signo, len(PROCESSES)))

    for p in PROCESSES:
        p.terminate()

class Reactor:

    """Main manager process"""

    def __init__(self):
        LOG.info('starting Health Tracker...')

        global PROCESSES
    
        # probe requests are put on this queue by Tracker 
        # to be consumed by Prober processes 
        self._probe_request_queue = multiprocessing.Queue()

        # processed probes are put on this queue by Prober processes to be 
        # consumed by Tracker
        self._probe_response_queue = multiprocessing.Queue()

        # instantiate Tracker
        self._tracker = Tracker(
            probe_request_queue=self._probe_request_queue,
            probe_response_queue=self._probe_response_queue)
        PROCESSES.append(self._tracker)

        # instantiate Probers
        for i in range(polaris.config.base['health_tracker']['probers']):
            p = Prober(
                probe_request_queue=self._probe_request_queue,
                probe_response_queue=self._probe_response_queue)
            PROCESSES.append(p)

        # start all processes
        for p in PROCESSES:
            p.start()

        # record the total number of child processes started 
        self._procs_total = len(PROCESSES)

        # shared memory client
        self._sm = memcache.Client(
            [polaris.config.shared_mem['hostname']])

        # trap the signal to terminate upon
        signal.signal(signal.SIGHUP, sig_handler)

        # write pid file
        LOG.debug('writting {}'.format(
            polaris.config.base['health_tracker']['pid_file']))    
        with open(polaris.config.base['health_tracker']['pid_file'], 'w') \
                as fh:
            fh.write(str(os.getpid()))

        # run the heartbeat loop
        self._heartbeat_loop()

        # remove pid file
        LOG.debug('removing {}'.format(
            polaris.config.base['health_tracker']['pid_file']))
        os.remove(polaris.config.base['health_tracker']['pid_file'])

        LOG.info('Health Tracker finished execution')

    def _heartbeat_loop(self):
        """Periodically log various application internal stats
        to a shared memory
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

            if alive == 0:
                # no processes are alive, join them and return
                for p in PROCESSES:
                    p.join()
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
                self._sm.set(polaris.config.shared_mem['health_heartbeat_key'],
                             json.dumps(obj), HEARTBEAT_TTL)
                LOG.debug('pushed heartbeat to shared mem')

                t_last = t_now

            time.sleep(HEARTBEAT_LOOP_INTERVAL)

