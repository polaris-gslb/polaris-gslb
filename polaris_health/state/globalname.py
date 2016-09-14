# -*- coding: utf-8 -*-

import logging

from polaris_health import Error

__all__ = [ 'GlobalName' ]

LOG = logging.getLogger(__name__)
LOG.addHandler(logging.NullHandler())

MAX_NAME_LEN = 256
MAX_POOL_NAME_LEN = 256
MIN_TTL = 1

class GlobalName:

    """Load-balnced DNS name"""

    def __init__(self, name, pool_name, ttl, nsrecord):
        """
        args:
            name: str, DNS name to be load-balanced
            pool_name: str, name of a pool to load balance against
            ttl: int, ttl value to return with responses

        """
        # name
        self.name = name.lower() # lowcase fqdns
        if (not isinstance(name, str) or len(name) == 0
                or len(name) > MAX_NAME_LEN):
            log_msg = ('name "{}" must be a non-empty str, {} chars max'
                       .format(name, MAX_NAME_LEN))
            LOG.error(log_msg)
            raise Error(log_msg)

        # pool_name
        self.pool_name = pool_name
        if (not isinstance(pool_name, str) or len(pool_name) == 0
                or len(pool_name) > MAX_POOL_NAME_LEN):
            log_msg = ('pool_name "{}" must be a non-empty str, {} chars max'
                       .format(pool_name, MAX_POOL_NAME_LEN))
            LOG.error(log_msg)
            raise Error(log_msg)

        # ttl
        self.ttl = ttl
        if (not isinstance(ttl, int) or ttl < MIN_TTL):
            log_msg = ('ttl must be an int greater or equal {}'
                       .format(ttl, MIN_TTL))
            LOG.error(log_msg)
            raise Error(log_msg)

        self.nsrecord = nsrecord

    @classmethod
    def from_config_dict(cls, name, obj):
        """Build a GlobalName object from a config dict.

        args:
            name: str, name of the globalname
            obj: dict, config dict

        """
        if 'pool' not in obj:
            log_msg = ('"{}" is missing a mandatory parameter "pool"'
                       .format(name))
            LOG.error(log_msg)
            raise Error(log_msg)

        if 'ttl' not in obj:
            log_msg = ('"{}" is missing a mandatory parameter "ttl"'
                       .format(name))
            LOG.error(log_msg)
            raise Error(log_msg)

        if 'nsrecord' not in obj:
            nsrecord_val=False
        else:
            nsrecord_val=obj['nsrecord']

        return cls(name=name, pool_name=obj['pool'], ttl=obj['ttl'], nsrecord=nsrecord_val)

    def to_dist_dict(self):
        """Return a dict representation of the GlobalName required by
        Polaris PDNS to perform distribution.

        Example:
            {
                'pool_name': 'pool1',
                'ttl': 1
            }

        """
        obj = {}
        obj['pool_name'] = self.pool_name
        obj['ttl'] = self.ttl
        obj['nsrecord'] = self.nsrecord

        return obj

