# -*- coding: utf-8 -*-

import logging
import multiprocessing

LOG = logging.getLogger(__name__)
LOG.addHandler(logging.NullHandler())

class Prober(multiprocessing.Process):

    """Prober process, consumes probe requests from a probe request queue,
    runs associated code and puts result onto a probe response queue.
    """

    def __init__(self, probe_request_queue, probe_response_queue):
        super(Prober, self).__init__()

        self.probe_request_queue = probe_request_queue
        self.probe_response_queue = probe_response_queue

    def run(self):
        while True:
            # grab the next Probe() from the queue 
            probe = self.probe_request_queue.get()

            # run the probe
            probe.run()

            # put the Probe() on the response queue
            self.probe_response_queue.put(probe)

