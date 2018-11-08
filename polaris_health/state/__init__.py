# -*- coding: utf-8 -*-
import logging
import time
import random
import heapq

from polaris_health import Error
from .pool import Pool, PoolMember
from .globalname import GlobalName


__all__ = [ 'State' ]

LOG = logging.getLogger(__name__)
LOG.addHandler(logging.NullHandler())

# seconds to randomly spread probes over initially
DISPERSION_WINDOW = 2


class PQItem:
    """Encapsulating type to facilitate the priority queue implementation,
    specifically, __lt__() method is required to manage objects with 
    same priority.
    """
    def __init__(self, pool_id, member_id):
        self.pool_id = pool_id
        self.member_id = member_id

    def __lt__(self, other):
        return self.member_id < other.member_id

class State:
    """Health state table 
    
    attributes:
        .pools
        .globalnames
    """    

    def __init__(self, config_obj):
        # build the state object from a config dict
        self._from_config_dict(config_obj)

        # set every member.retries_left to their parent's pool monitor retries
        for pool_name, pool in self.pools.items():
            for member in pool.members:
                member.retries_left = pool.monitor.retries

        # build a list of all pools members used in determining
        # the health status convergence progress
        self._status_undetermined = []
        for pool_name in self.pools:
            for member in self.pools[pool_name].members:
                self._status_undetermined.append(member)


        # build lookup tables used in the health checking process
        self._pool_by_id = []
        self._member_by_id = []
        for pool_name, pool in self.pools.items():
            pool._id = len(self._pool_by_id)
            self._pool_by_id.append(pool)
            for member in pool.members:
                member._id = len(self._member_by_id)
                self._member_by_id.append(member)

        # build priority queue used for probes scheduling
        # the queue is a list of (prio, PQItem) tuples
        self._pq = []
        for pool_name, pool in self.pools.items():
            for member in pool.members:
                # disperse the probes start time over a small window
                # so they don't all fire off at once causing cpu spikes
                next_probe_monotime = time.monotonic() + \
                        random.uniform(0, DISPERSION_WINDOW)
                heapq.heappush(self._pq,
                        (next_probe_monotime, 
                        PQItem(pool_id=pool._id, member_id=member._id)))

    @property
    def health_converged(self):
        """Return True if all pools members status has been
        determined(not None), False otherwise.
        """
        # all pools members status is determined
        if len(self._status_undetermined) == 0:
            return True

        while len(self._status_undetermined) > 0:
            if self._status_undetermined[0].status is None:
                    return False
            self._status_undetermined.pop(0)

        LOG.info("health status convergence complete") 
        return True

    def to_dist_dict(self):
        """Return a dict representation of self required by Polaris PDNS
        to perform query distribution.

        """
        obj = {}

        # add a timestamp
        obj['timestamp'] = time.time()

        # add pools
        obj['pools'] = {}
        for pool_name in self.pools:
            obj['pools'][pool_name] = self.pools[pool_name].to_dist_dict()

        # add globalnames
        obj['globalnames'] = {}
        for globalname_name in self.globalnames:
            obj['globalnames'][globalname_name] = \
                self.globalnames[globalname_name].to_dist_dict()

        return obj

    def _from_config_dict(self, obj):    
        """Initialize State from a config dict

        args:
            obj: dict, config dict(lb_config)

        """
        # build pools 
        self.pools = {}
        if 'pools' not in obj or not obj['pools']:
            log_msg = 'configuration must have pools'
            LOG.error(log_msg)
            raise Error(log_msg)

        for pool_name in obj['pools']:
            # check if pool with the same name has been defined earlier
            if pool_name in self.pools:
                log_str = 'pool "{}" already exists'.format(pool_name)
                LOG.error(log_str)
                raise Error(log_str)

            self.pools[pool_name] = \
                    Pool.from_config_dict(pool_name=pool_name,
                                          obj=obj['pools'][pool_name])
        
        # build globalnames
        self.globalnames = {}
        if 'globalnames' not in obj or not obj['globalnames']:
            log_msg = 'configuration must have globalnames'
            LOG.error(log_msg)
            raise Error(log_msg)

        for globalname_name in obj['globalnames']:
                # check if globalname with the same name 
                # has been defined earlier
                if globalname_name in self.globalnames:
                    log_str = ('globalname "{}" already exists'
                               .format(globalname_name))
                    LOG.Error(log_msg)
                    raise Error(log_msg)    

                # check if the referenced pool exists
                if 'pool' not in obj['globalnames'][globalname_name]:
                    log_msg = ('"{}" is missing a mandatory parameter "pool"'
                               .format(globalname_name))
                    LOG.error(log_msg)
                    raise Error(log_msg)
                else:      
                    pool_name = obj['globalnames'][globalname_name]['pool']

                if pool_name not in self.pools:
                    log_msg = ('globalname "{}" references unknown pool "{}"'.
                               format(globalname_name, pool_name))
                    LOG.error(log_msg)
                    raise Error(log_msg)

                self.globalnames[globalname_name] = \
                    GlobalName.from_config_dict(
                        name=globalname_name,
                        obj=obj['globalnames'][globalname_name])   

