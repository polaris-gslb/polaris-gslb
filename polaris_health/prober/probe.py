# -*- coding: utf-8 -*-

import logging
import time
import sys

from polaris_health import MonitorFailed


__all__ = [ 'Probe' ]

LOG = logging.getLogger(__name__)
LOG.addHandler(logging.NullHandler())


class Probe(object):

    """Health monitor probe"""

    def __init__(self, pool_name, member_ip, monitor, monitor_ip):
        """
        args:
            pool_name: string, name of the pool
            member_ip: string, IP address
            monitor: monitors.BaseMonitor derived object
            monitor_ip: string, destination IP address to use for monitor
        """
        self.pool_name = pool_name
        self.member_ip = member_ip
        self.monitor = monitor
        self.monitor_ip = monitor_ip

        # None, True - probe succeded, False - probe failed
        self.status = None

        # reason for the status
        self.status_reason = None

        # when status was recorded
        self.status_time = None

    def run(self):
        """Run the monitor code"""
        try:
            self.monitor.run(dst_ip=self.monitor_ip)
        except MonitorFailed as e:
            # if monitor failed status = False
            self.status = False
            self.status_reason =  str(e)
            self.status_time = time.time()
        # protect the app from crashing if a monitor crashes
        except Exception as e:
            self.status = False
            self.status_reason =  str(e)
            self.status_time = time.time()
            LOG.exception('{} crashed:\n{}'.format(str(self), e))

        # monitor passed
        else:
            self.status = True
            self.status_reason = "monitor passed"

        # record time when the status was recorded
        self.status_time = time.time()

    def __str__(self):
        s = 'Probe('
        s += ('pool: {pool_name} '
              'member_ip: {member_ip} '
              'monitor: {monitor} '
              'monitor_ip: {monitor_ip} '
              'status: {status} '
              'status_reason: {status_reason} '
              'status_time: {status_time})'
              .format(pool_name=self.pool_name, 
                      member_ip=self.member_ip, 
                      monitor=self.monitor.__class__.__name__,
                      monitor_ip=self.monitor_ip,
                      status=self.status, 
                      status_reason=self.status_reason, 
                      status_time=self.status_time))
        return s

