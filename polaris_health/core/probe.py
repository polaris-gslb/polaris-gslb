# -*- coding: utf-8 -*-

import logging
import time

from polaris_health import MonitorFailed

__all__ = [ 'Probe' ]

LOG = logging.getLogger(__name__)
LOG.addHandler(logging.NullHandler())

class Probe(object):

    """Health monitor probe"""

    def __init__(self, pool_name, member_ip, monitor):
        """
        args:
            pool_name: string, name of the pool
            member_ip: string
            monitor: monitors.BaseMonitor derived object
        """
        self.pool_name = pool_name
        self.member_ip = member_ip
        self.monitor = monitor

        # None, True - probe succeded, False - probe failed
        self.status = None

        # reason for the status
        self.status_reason = None

        # when status was recorded
        self.status_time = None

    def run(self):
        """Run the monitor code"""

        try:
            # run monitor on member_ip
            self.monitor.run(dst_ip=self.member_ip)
        except MonitorFailed as e:
            # if monitor failed status = False
            self.status = False
            self.status_reason =  str(e)
            self.status_time = time.time()

            LOG.debug('{} failed'.format(str(self)))
        
        # protect the app from crashing if a monitor crashes
        except Exception as e:
            self.status = False
            self.status_reason =  str(e)
            self.status_time = time.time()
            LOG.error('{} crashed'.format(str(self)))

        # monitor passed
        else:
            self.status = True
            self.status_reason = "monitor passed"

        # record time when the status was recorded
        self.status_time = time.time()

    def __str__(self):
        s = 'Probe('
        s += ('pool: {} member_ip: {} monitor: {} status: {} '
              'status_reason: {} status_time: {})'
              .format(self.pool_name, self.member_ip, 
                      self.monitor.__class__.__name__, 
                      self.status, self.status_reason, self.status_time))
        return s

