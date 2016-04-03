# -*- coding: utf-8 -*-

import logging

import memcache


__all__ = [ 'MemcacheClient' ]

LOG = logging.getLogger(__name__)
LOG.addHandler(logging.NullHandler())


class MemcacheClient:

    """Memcache client wrapper"""

    def __init__(self, servers, dead_retry=0, socket_timeout=0.5, 
                 server_max_value_length=1024*1024):
        self.servers = servers
        self.dead_retry = dead_retry
        self.socket_timeout = socket_timeout
        self.server_max_value_length = server_max_value_length

        self._client = memcache.Client(
            servers=servers,
            dead_retry=dead_retry,
            socket_timeout=socket_timeout,
            server_max_value_length=server_max_value_length)

    def set(self, *args, **kwargs):
        """on success return bool True, on failure return int 0""" 
        try:
            return self._client.set(*args, **kwargs)
        except Exception as e:
            return int(0)
            
    def get(self, *args, **kwargs):
        """on success return value, on failure return bool None"""
        try:
            return self._client.get(*args, **kwargs)
        except Exception as e:
            return None

