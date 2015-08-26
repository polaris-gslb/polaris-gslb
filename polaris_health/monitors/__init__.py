# -*- coding: utf-8 -*-

import logging

from polaris_health import Error

__all__ = [ 
           'BaseMonitor',
           'registered'
           ]

LOG = logging.getLogger(__name__)
LOG.addHandler(logging.NullHandler())

# allowed ranges
MIN_INTERVAL = 1
MAX_INTERVAL = 3600
MIN_TIMEOUT = 0.1
MAX_TIMEOUT = 5
MIN_RETRIES = 0
MAX_RETRIES = 5

class BaseMonitor:

    """Base monitor"""

    def __init__(self, interval, timeout, retries):
        # interval
        if (not isinstance(interval, (int, float)) 
                or interval < MIN_INTERVAL 
                or interval > MAX_INTERVAL):
            log_msg = ('interval "{}" must be a number between {} and {}'.
                       format(interval, MIN_INTERVAL, MAX_INTERVAL))
            raise Error(log_msg)
        else:
            self.interval = interval

        # timeout
        if (not isinstance(timeout, (int, float)) 
                or timeout < MIN_TIMEOUT 
                or timeout > MAX_TIMEOUT):
            log_msg = ('timeout "{}" must be a number between {} and {}'.
                       format(timeout, MIN_TIMEOUT, MAX_TIMEOUT))
            raise Error(log_msg)
        else:
            self.timeout = timeout

        # retries
        if (not isinstance(retries, int) 
                or retries < MIN_RETRIES 
                or retries > MAX_RETRIES):
            log_msg = ('retries "{}" must be an int between {} and {}'.
                       format(retries, MIN_RETRIES, MAX_RETRIES))
            raise Error(log_msg)
        else:
            self.retries = retries

    def run(self, dst_ip):
        raise NotImplementedError

    def __str__(self):
        s = '{} '.format(self.__class__.__name__)
        for k in self.__dict__:
            s += '{}={} '.format(k, self.__dict__[k])
        return s

from .http import HTTPStatus, HTTPSStatus
from .tcp import TCPConnect, TCPContent

registered = {
    'http_status': HTTPStatus,
    'https_status': HTTPSStatus,
    'tcp_connect': TCPConnect,
    'tcp_content': TCPContent
}            

