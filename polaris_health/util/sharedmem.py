# -*- coding: utf-8 -*-

import logging

import memcache

from polaris_health import config


__all__ = [ 'Client' ]

LOG = logging.getLogger(__name__)
LOG.addHandler(logging.NullHandler())


class Client:

    """Memcache client."""

    def __init__(self):
        # dead_retry - number of seconds before retrying a blacklisted server
        self._client = memcache.Client(
            [config.BASE['SHARED_MEM_HOSTNAME']],
            dead_retry=0, 
            socket_timeout=config.BASE['SHARED_MEM_SOCKET_TIMEOUT'],
            server_max_value_length=config.BASE['SHARED_MEM_SERVER_MAX_VALUE_LENGTH'])

    def set(self, *args, **kwargs):
        return self._client.set(*args, **kwargs)

    def get(self, *args, **kwargs):
        return self._client.get(*args, **kwargs)

