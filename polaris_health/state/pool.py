# -*- coding: utf-8 -*-

import logging
import ipaddress
import random

import polaris_health.config
from polaris_health.util import topology
from polaris_health import Error, monitors

__all__ = [ 'PoolMember', 'Pool' ]

LOG = logging.getLogger(__name__)
LOG.addHandler(logging.NullHandler())

MAX_POOL_MEMBER_NAME_LEN = 256
MAX_POOL_MEMBER_WEIGHT = 99
MAX_POOL_NAME_LEN = 256
MAX_REGION_LEN = 256
MAX_MAX_ADDRS_RETURNED = 32

def pprint_status(status):
    """convert a bool into a server status string"""

    if status is True:
        return 'UP'
    elif status is False:
        return 'DOWN'
    elif status is None:
        return 'NEW/UNKNOWN'
    else:
        raise Error('Invalid status "{}"'.format(status))

class PoolMember:

    """A backend server, member of a pool"""

    def __init__(self, ip, name, weight, region=None):
        """
        args:
            ip: string, IP address
            name: string, name of the server
            weight: int, weight of the server, if set to 0 the server
                is disabled
            region: string, id of the region, used in topology-based 
                distribution
        """
        ### ip
        try:
            _ip = ipaddress.ip_address(ip)
        except ValueError:
            log_msg = ('"{}" does not appear to be a valid IP address'
                       .format(ip))
            LOG.error(log_msg)
            raise Error(log_msg)

        if _ip.version != 4:
            log_msg = 'only v4 IP addresses are supported'
            LOG.error(log_msg)
            raise Error(log_msg)

        self.ip = ip

        ### name
        if (not isinstance(name, str) or len(name) > MAX_POOL_MEMBER_NAME_LEN):
            log_msg = ('"{}" name must be a str, {} chars max'.
                       format(name, MAX_POOL_MEMBER_NAME_LEN))
            LOG.error(log_msg)
            raise Error(log_msg)
        else:
            self.name = name

        ### weight    
        if (not isinstance(weight, int) or weight < 0 
                or weight > MAX_POOL_MEMBER_WEIGHT):
            log_msg = ('"{}" weight "{}" must be an int between 0 and {}'.
                       format(name, weight, MAX_POOL_MEMBER_WEIGHT))
            raise Error(log_msg)
        else:
            self.weight = weight

        ### region
        if (not region is None 
                and (not isinstance(region, (str)) 
                 or len(region) > MAX_REGION_LEN)):
            log_msg = ('"{}" region "{}" must be a str, {} chars max'.
                       format(name, region, MAX_POOL_MEMBER_NAME_LEN))
            LOG.error(log_msg)
            raise Error(log_msg)
        else:
            self.region = region          

        # curent status of the server
        # None = new, True = up, False = down
        self.status = None

        # reason why this status has been set
        self.status_reason = None

        # timestamp when the probe was issued last time
        # used to determine when to send a new probe
        self.last_probe_issued_time = None

        # this is used by tracker to determine how many more
        # probing requests to attempt before declaring the member down
        # set to the parent's pool monitor retries value initially
        self.retries_left = None

class Pool:

    """A pool of backend servers"""

    LB_METHOD_OPTIONS = [ 'wrr', 'twrr' ]
    FALLBACK_OPTIONS = [ 'any', 'refuse', 'nodata' ]

    def __init__(self, name, monitor, members, lb_method,
                 fallback='any', max_addrs_returned=1):
        """
        args:
            name: string, name of the pool
            monitor: obj derived from monitors.BaseMonitor
            members: dict where keys are IP addresses of members,
                values are PoolMember objects
            lb_method: string, distribution method name
            fallback: sring, one of "any", "nodata", "refuse"
                resolution behaviour when all members of the pool are DOWN
                "any": perform distribution amongst all configured
                    members(ignore health status)
                "refuse": refuse queries
                "nodata": return an empty RR-set
            max_addrs_returned: int, max number of A records to return in
                response
        """
        ### name
        if (not isinstance(name, str) 
                or len(name) > MAX_POOL_NAME_LEN):
            log_msg = ('"{}" name must be a str, {} chars max'.
                       format(name, MAX_POOL_NAME_LEN))
            LOG.error(log_msg)
            raise Error(log_msg)
        else:
            self.name = name

        ### monitor
        self.monitor = monitor

        ### members
        self.members = members

        ### lb_method
        if (not isinstance(lb_method, str) 
                or lb_method not in self.LB_METHOD_OPTIONS):
            _lb_methods = ', '.join(self.LB_METHOD_OPTIONS)
            log_msg = ('lb_method "{}" must be a str one of {}'.
                       format(lb_method, _lb_methods)) 
            LOG.error(log_msg)         
            raise Error(log_msg)
        else:
            self.lb_method = lb_method

        ### fallback
        if (not isinstance(fallback, str) 
                or fallback not in self.FALLBACK_OPTIONS):
            _fallbacks = ', '.join(self.FALLBACK_OPTIONS)
            log_msg = ('fallback "{}" must be a str one of {}'.
                       format(fallback, _fallbacks))
            LOG.error(log_msg)         
            raise Error(log_msg)
        else:
            self.fallback = fallback      

        # max_addrs_returned    
        if (not isinstance(max_addrs_returned, int) or max_addrs_returned < 1 
                or max_addrs_returned > MAX_MAX_ADDRS_RETURNED):
            log_msg = ('"{}" max_addrs_returned "{}" must be an int '
                       'between 1 and {}'
                       .format(name, max_addrs_returned, 
                               MAX_MAX_ADDRS_RETURNED))
            raise Error(log_msg)
        else:
            self.max_addrs_returned = max_addrs_returned

        # last known status None, True, False
        self.last_status = None

    ########################   
    ### public interface ###
    ########################
    @property
    def status(self):
        """Return health status of the pool.

        Read-only property based on health status of the pool members.

        Return True is any member of the pool is UP, False otherwise.
        """
        for member_ip in self.members:
            if self.members[member_ip].status:
                return True

        return False

    @classmethod
    def from_config_dict(cls, name, obj):
        """Build a Pool object from a config dict

        args:
            name: string, name of the pool
            obj: dict, config dict
        """

        ############################
        ### mandatory parameters ###
        ############################

        ### monitor
        if obj['monitor'] not in monitors.registered:
            log_msg = 'unknown monitor "{}"'.format(obj['monitor'])
            LOG.error(log_msg)
            raise Error(log_msg)
        else:
            monitor_name = obj['monitor']

        if 'monitor_params' in obj:
            if not obj['monitor_params']:
                log_msg = 'monitor_params should not be empty'
                LOG.error(log_msg)
                raise Error(log_msg)

            monitor_params = obj['monitor_params']
        else:
            monitor_params = {}
                 
        monitor = monitors.registered[monitor_name](**monitor_params)

        ### lb_method
        lb_method = obj['lb_method']

        ### members
        members = {}

        # validate "members" key is present and not empty
        if not 'members' in obj or not obj['members']:
            log_msg = ('configuration dictionary must contain '
                       'a non-empty "members" key')    
            LOG.error(log_msg)
            raise Error(log_msg)

        for member_ip in obj['members']:
            member_name = obj['members'][member_ip]['name']
            weight = obj['members'][member_ip]['weight']

            region = None
            # if topology round robin method is used
            # set region on the pool member
            if lb_method == 'twrr':
                region = topology.get_region(
                    member_ip, polaris_health.config.TOPOLOGY_MAP)
                if not region:
                    log_msg  = ('Unable to determine region for pool '
                                '{0} member {1}({2})'.
                               format(name, member_ip, member_name)) 
                    LOG.error(log_msg)
                    raise Error(log_msg)

            members[member_ip] = PoolMember(ip=member_ip, 
                                            name=member_name, 
                                            weight=weight,
                                            region=region)

        ###########################
        ### optional parameters ###
        ###########################
        pool_optional_params = {}

        ### fallback
        if 'fallback' in obj:
            pool_optional_params['fallback'] = obj['fallback']

        ### max_addrs_returned
        if 'max_addrs_returned' in obj:
            pool_optional_params['max_addrs_returned'] = \
                obj['max_addrs_returned']

        # return Pool object
        return cls(name=name,
                   monitor=monitor,
                   lb_method=lb_method,
                   members=members,
                   **pool_optional_params)

    def to_dist_dict(self):
        """Return dict representation of the Pool required to perform 
        distribution.

        "_default" distribution table is always built.

        If a topology-based lb method is used, also build regional 
        distribution tables.

        Example:
            {
                'status' : True,
                'lb_method': 'twrr',
                'max_addrs_returned': 1,
                'dist_tables': {
                    '_default': {
                        'rotation': [ '192.168.1.1', '192.168.1.2' ],
                        'num_unique_addrs': 2,
                        'index': 1
                    },

                    'region1': {
                        'rotation': [ '192.168.1.1' ],
                        'num_unique_addrs': 1,
                        'index': 0
                    },

                    'region2': {
                        'rotation': [ '192.168.1.2' ],
                        'num_unique_addrs': 1,
                        'index': 0
                    },
                }
            }

        """
        obj = {}

        ### status
        obj['status'] = self.status

        ### lb_method  
        obj['lb_method'] = self.lb_method

        ### max_addrs_returned
        obj['max_addrs_returned'] = self.max_addrs_returned

        ### distribution tables
        dist_tables = {} 

        # always build the _default distribution table
        dist_tables['_default'] = {}
        dist_tables['_default']['rotation'] = []
        dist_tables['_default']['num_unique_addrs'] = 0
        
        for member_ip in self.members:
            member = self.members[member_ip]

            # ignore members with weight of 0 - member is disabled
            if member.weight == 0:
                continue

            # add the member IP times it's weight into 
            # the_default distribution table
            for i in range(member.weight):
                dist_tables['_default']['rotation'].append(member_ip)
                # increase the number of unique addresses

            # increase the number of unique addresses in the _default by __1__
            dist_tables['_default']['num_unique_addrs'] += 1

            # if a topology lb method is used and the member is UP 
            # add it to a corresponding regiinal table 
            if self.lb_method == 'twrr' and member.status:
                # create the regional table if it does not exist
                if member.region not in dist_tables:
                    dist_tables[member.region] = {}
                    dist_tables[member.region]['rotation'] = []
                    dist_tables[member.region]['num_unique_addrs'] = 0

                # add the member IP it's weight into the regional table
                for i in range(member.weight):
                    dist_tables[member.region]['rotation'].append(member_ip)

                # increase the number of unique addresses in the table by __1__
                dist_tables[member.region]['num_unique_addrs'] += 1

        for name in dist_tables:
            # randomly shuffle the rotation list
            random.shuffle(dist_tables[name]['rotation']) 
       
            # create index used by distributor for distribution,
            # set it to a random position, when distributor is
            # syncing its internal state from shared memory, indexes gets
            # reset, we want to avoid starting from 0 every time
            dist_tables[name]['index'] = \
                int(random.random() * len(dist_tables[name]['rotation'])) 

        obj['dist_tables'] = dist_tables

        return obj

