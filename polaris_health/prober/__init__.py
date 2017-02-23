# -*- coding: utf-8 -*-

import logging
import time
import multiprocessing
import threading
import queue

from polaris_health import MonitorFailed


__all__ = [ 'ProberProcess', 'ProberThread' ]

LOG = logging.getLogger(__name__)
LOG.addHandler(logging.NullHandler())

# block prober requests queue read with a small timeout so we don't eat
# CPU needlessly at low message rate    
PROBER_REQUESTS_QUEUE_GET_TIMEOUT = 0.01

# the number of prober threads to start initially per Prober process
INITIAL_PROBER_THREADS = 25
# maximum number of threads allowed per Prober process 
MAX_PROBER_THREADS = 500
# how often to run the logic that terminates excessive threads
CLEANUP_THREADS_INTERVAL = 30
# at what number of excessive threads to begin to terminate them
EXCESSIVE_THREADS_THRESHOLD = 25

# counter updated by Prober threads showing how many of them 
# are currently processing health probes
_THREADS_BUSY = 0


class ProberProcess(multiprocessing.Process):

    """Prober process.

    Consumes probe requests from a prober requests queue, passes them on to 
    Prober threads, receives probe responses from Prober threads and
    puts them onto a prober responses queue.

    Implements dynamic thread scheduling:
        - when a probe request is received and all the existing threads are
        busy, additional threads are created.
        - based on the max number of busy threads over a period of 
        time excessive threads are terminated.
    """

    def __init__(self, prober_requests, prober_responses):
        super(ProberProcess, self).__init__()

        # Guardian-created queues to pass probes between Tracker 
        # and Prober processes    
        self.prober_requests = prober_requests
        self.prober_responses = prober_responses

        # Prober process-local queues to communicate with Prober Threads
        self.thread_requests = queue.Queue()
        self.thread_responses = queue.Queue()

        # synchronization object used by threads to update _THREADS_BUSY
        self.threads_busy_lock = threading.Lock()

        # pool of threads managed by the Prober
        self._threads = []

        # maximum number of of busy threads over CLEANUP_THREADS_INTERVAL 
        self._max_busy_threads = 0

    def run(self):
        # create a number of initial threads    
        for i in range(INITIAL_PROBER_THREADS):
            self._spinathread()

        t_last = time.monotonic()
        while True:
            self._process_probe_request()
            self._process_probe_response()

            if self._max_busy_threads < _THREADS_BUSY:
                self._max_busy_threads = _THREADS_BUSY        

            if time.monotonic() - t_last > CLEANUP_THREADS_INTERVAL:
                self._cleanup_threads()
                # reset the value for the next cleanup period
                self._max_busy_threads = 0
                t_last = time.monotonic()

    def _process_probe_request(self):
            """Read a probe request sent by the Tracker from the prober
            requests queue, verify that there are threads available to 
            do the work, spin an additional thread if needed, pass the 
            probe request to Probe threads via thread requests queue.
            """
            try:
                probe_request = self.prober_requests.get(
                    block=True, timeout=PROBER_REQUESTS_QUEUE_GET_TIMEOUT)
            except queue.Empty:
                # did not get a probe request within the timeout
                return
            
            # got a probe request
            if len(self._threads) - _THREADS_BUSY <= 0:
                LOG.debug('all threads are busy, '
                          'spinning an additional thread')
                self._spinathread()
            self.thread_requests.put(probe_request)

    def _process_probe_response(self):
            """If available read a probe response from the Prober threads
            and send it to the Tracker via the prober responses queue.
            """
            try:
                probe_response = self.thread_responses.get(block=False) 
            except queue.Empty:
                # no probe response on the queue
                pass
            else:
                # got a probe response
                self.prober_responses.put(probe_response)

    def _cleanup_threads(self):
        """Join any threads that finished the execution.
        Validate if there are too many threads running and terminate 
        excessive threads.
        """
        LOG.debug('running threads cleanup, threads '
                  'total: {total} max busy: {max_busy}'
                  .format(total=len(self._threads), 
                          max_busy=self._max_busy_threads))

        # join exited threads
        remove_list = []
        for t in self._threads:
            if not t.is_alive():
                t.join()
                remove_list.append(t)    

        # remove joined threads from self._threads
        if remove_list:
            for t in remove_list:
                self._threads.remove(t)

        if len(self._threads) - self._max_busy_threads >= \
                EXCESSIVE_THREADS_THRESHOLD:
            num_to_kill = len(self._threads) - self._max_busy_threads - 1
            LOG.debug('excessive threads detected, '
                      'total: {total} max busy: {max_busy}, '
                      'scheduling termination of {num_to_kill} threads'
                      .format(total=len(self._threads), 
                              max_busy=self._max_busy_threads,
                              num_to_kill=num_to_kill)) 
            # command excessive threads to exit by sending a poison pill
            for i in range(num_to_kill):
                self.thread_requests.put(None)

    def _spinathread(self):
        """Start up a new Prober thread"""
        if len(self._threads) >= MAX_PROBER_THREADS:
            LOG.warning('reached Prober threads limit, '
                        'unable to spin more threads')
        else:
            t = ProberThread(thread_requests=self.thread_requests,
                             thread_responses=self.thread_responses,
                             threads_busy_lock=self.threads_busy_lock)
            self._threads.append(t)
            t.start()

class ProberThread(threading.Thread):

    """Prober thread, consumes probe requests from thread requests queue,
    runs associated code and puts result onto thread responses queue.
    """

    def __init__(self, thread_requests, thread_responses, 
                 threads_busy_lock):
        super(ProberThread, self).__init__()

        # flag the thread as daemon so it's abruptly killed when
        # its parent process exists
        self.daemon = True

        self.thread_requests = thread_requests
        self.thread_responses = thread_responses
        self.threads_busy_lock = threads_busy_lock

    def run(self):
        global _THREADS_BUSY

        while True:
            probe = self.thread_requests.get()
           
            # poison pill, exit
            if probe == None:
                return

            with self.threads_busy_lock:
                _THREADS_BUSY += 1

            # run the probe
            probe.run()

            # put the Probe() on the response queue
            self.thread_responses.put(probe)

            with self.threads_busy_lock:
                _THREADS_BUSY -= 1

