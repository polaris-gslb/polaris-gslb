# -*- coding: utf-8 -*-

import logging
import time
import sys

from polaris_health import MonitorFailed


__all__ = [ 'Probe' ]

LOG = logging.getLogger(__name__)
LOG.addHandler(logging.NullHandler())


class Probe(object):

    """Health check probe"""

    def __init__(self, pool_id, pool_name, member_id, member_ip, 
                 monitor, monitor_ip):
        """
        args:
            pool_id: State._pool_by_id index
            pool_name: String, name of the pool
            member_id: State._member_by_id index
            member_ip: String, IP of the member
            monitor: monitors.BaseMonitor derived object
            monitor_ip: string, destination IP address to use for monitor
        """
        self.pool_id = pool_id
        self.pool_name = pool_name
        self.member_id = member_id
        self.member_ip = member_ip
        self.monitor = monitor
        self.monitor_ip = monitor_ip

        # None - init, True - probe succeeded, False - probe failed
        self.status = None

        # reason for the status
        self.status_reason = None

    def run(self):
        """Run the monitor code"""
        try:
            self.monitor.run(dst_ip=self.monitor_ip)
        except MonitorFailed as e:
            # if the monitor has failed set status to False
            self.status = False
            self.status_reason =  str(e)
        # protect the app from crashing if the monitor crashes
        except Exception as e:
            self.status = False
            self.status_reason = str(e)
            LOG.exception('{} crashed:\n{}'.format(str(self), e))
        # monitor passed
        else:
            self.status = True
            self.status_reason = "monitor passed"

    def __str__(self):
        s = 'Probe('
        s += ('pool: {pool_name} '
              'member_ip: {member_ip} '
              'monitor: {monitor} '
              'monitor_ip: {monitor_ip} '
              'status: {status} '
              'status_reason: {status_reason} '
              .format(pool_name=self.pool_name, 
                      member_ip=self.member_ip, 
                      monitor=self.monitor.__class__.__name__,
                      monitor_ip=self.monitor_ip,
                      status=self.status, 
                      status_reason=self.status_reason)) 
        return s

