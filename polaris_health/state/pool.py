# -*- coding: utf-8 -*-

import logging
import ipaddress
import random

from polaris_health import Error, config, monitors
from polaris_common import topology


__all__ = [ 'PoolMember', 'Pool' ]

LOG = logging.getLogger(__name__)
LOG.addHandler(logging.NullHandler())

MAX_POOL_MEMBER_NAME_LEN = 256
MAX_POOL_MEMBER_WEIGHT = 99
MAX_POOL_NAME_LEN = 256
MAX_REGION_LEN = 256
MAX_MAX_ADDRS_RETURNED = 100


def pprint_status(status):
    """Convert bool status into a health status string"""

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
            log_msg = 'only v4 IP addresses are currently supported'
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

    LB_METHOD_OPTIONS = [ 'wrr', 'twrr', 'fogroup' ]
    FALLBACK_OPTIONS = [ 'any', 'refuse' ]

    def __init__(self, name, monitor, members, lb_method,
                 fallback='any', max_addrs_returned=1):
        """
        args:
            name: string, name of the pool
            monitor: obj, a subclass of monitors.BaseMonitor
            members: list of PoolMember objects
            lb_method: string, distribution method name
            fallback: sring, one of "any", "refuse"
                resolution behaviour when all members of the pool are DOWN
                "any": perform distribution amongst all configured
                    members(ignore health status)
                "refuse": refuse queries
            max_addrs_returned: int, max number of A records to return in
                response
        """
        ### name
        self.name = name
        if (not isinstance(name, str)
                or len(name) > MAX_POOL_NAME_LEN):
            log_msg = ('"{}" name must be a str, {} chars max'.
                       format(name, MAX_POOL_NAME_LEN))
            LOG.error(log_msg)
            raise Error(log_msg)

        ### monitor
        self.monitor = monitor

        ### members
        self.members = members

        ### lb_method
        self.lb_method = lb_method
        if (not isinstance(lb_method, str)
                or lb_method not in self.LB_METHOD_OPTIONS):
            _lb_methods = ', '.join(self.LB_METHOD_OPTIONS)
            log_msg = ('lb_method "{}" must be a str one of {}'.
                       format(lb_method, _lb_methods))
            LOG.error(log_msg)
            raise Error(log_msg)

        ### fallback
        self.fallback = fallback
        if (not isinstance(fallback, str)
                or fallback not in self.FALLBACK_OPTIONS):
            _fallbacks = ', '.join(self.FALLBACK_OPTIONS)
            log_msg = ('fallback "{}" must be a str one of {}'.
                       format(fallback, _fallbacks))
            LOG.error(log_msg)
            raise Error(log_msg)

        # max_addrs_returned
        self.max_addrs_returned = max_addrs_returned
        if (not isinstance(max_addrs_returned, int) or max_addrs_returned < 1
                or max_addrs_returned > MAX_MAX_ADDRS_RETURNED):
            log_msg = ('"{}" max_addrs_returned "{}" must be an int '
                       'between 1 and {}'
                       .format(name, max_addrs_returned,
                               MAX_MAX_ADDRS_RETURNED))
            raise Error(log_msg)

        # last known status None, True, False
        self.last_status = None

    ########################
    ### public interface ###
    ########################
    @property
    def status(self):
        """Return health status of the pool.

        Read-only property based on health status of the pool members.

        Return True if any member of the pool with a non-0 weight is UP,
        False otherwise.
        """
        for member in self.members:
            if member.weight > 0 and member.status:
                return True

        return False

    @classmethod
    def from_config_dict(cls, pool_name, obj):
        """Build a Pool object from a config dict

        args:
            pool_name: string, pool_name of the pool
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
        members = []

        # validate "members" key is present and not empty
        if not 'members' in obj or not obj['members']:
            log_msg = ('configuration dictionary must contain '
                       'a non-empty "members" list')
            LOG.error(log_msg)
            raise Error(log_msg)

        for member_obj in obj['members']:
            # ensure a member with the same IP doesn't exist already
            for _m in members:
                if member_obj['ip'] == _m.ip:
                    log_msg = 'duplicate member IP {}'.format(member_obj['ip'])
                    LOG.error(log_msg)
                    raise Error(log_msg)

            region = None
            # if topology lb method is used - set region on the pool member
            if lb_method == 'twrr':
                region = topology.get_region(
                    member_obj['ip'], config.TOPOLOGY_MAP)
                if not region:
                    log_msg  = ('unable to determine region for member {}({})'
                                .format(member_obj['ip'], member_obj['name']))
                    LOG.error(log_msg)
                    raise Error(log_msg)

            _m = PoolMember(ip=member_obj['ip'],
                            name=member_obj['name'],
                            weight=member_obj['weight'],
                            region=region)
            members.append(_m)

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
        return cls(name=pool_name,
                   monitor=monitor,
                   lb_method=lb_method,
                   members=members,
                   **pool_optional_params)

    def to_dist_dict(self):
        """Return dict representation of the Pool required by Polaris PDNS
        to perform query distribution.

        "_default" distribution table is always built.

        Region-specific distribution tables are built only if the pool is using
        a topology lb method and has an UP member.

        Example:
            {
                'status' : True,
                'lb_method': 'twrr',
                'fallback': 'any',
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

        ### fallback
        obj['fallback'] = self.fallback

        ### max_addrs_returned
        obj['max_addrs_returned'] = self.max_addrs_returned

        ### distribution tables
        dist_tables = {}

        # always build the _default distribution table
        dist_tables['_default'] = {}
        dist_tables['_default']['rotation'] = []
        dist_tables['_default']['names'] = []
        dist_tables['_default']['num_unique_addrs'] = 0

        ##################
        ### pool is UP ###
        ##################
        if self.status:
            for member in self.members:
                # do not add members with the weight of 0 - member is disabled
                if member.weight == 0:
                    continue

                # do not add members in DOWN state
                if not member.status:
                    continue

                #
                # add to the _default table
                #

                # add the member IP times it's weight into
                # the _default distribution table
                for i in range(member.weight):
                    dist_tables['_default']['rotation'].append(member.ip)
                    dist_tables['_default']['names'].append(member.name)

                # increase the number of unique addresses in the _default by 1
                dist_tables['_default']['num_unique_addrs'] += 1

                # if lb_method is failover group do not add any more members
                if self.lb_method == 'fogroup':
                    break

                #
                # add to a regional table
                #

                # if a topology lb method is used, add the member's IP
                # to a corresponding regional table
                if self.lb_method == 'twrr':
                    # create the regional table if it does not exist
                    if member.region not in dist_tables:
                        dist_tables[member.region] = {}
                        dist_tables[member.region]['rotation'] = []
                        dist_tables[member.region]['num_unique_addrs'] = 0

                    # add the member IP times it's weight
                    # into the regional table
                    for i in range(member.weight):
                        dist_tables[member.region]['rotation'].append(
                            member.ip)

                    # increase the number of unique addresses in the table by 1
                    dist_tables[member.region]['num_unique_addrs'] += 1

        ####################
        ### pool is DOWN ###
        ####################
        else:
            for member in self.members:
                # do not add members with weight of 0 - member is disabled
                if member.weight == 0:
                    continue

                # add to the _default table if fallback is set to 'any'
                if self.fallback == 'any':
                    # add the member IP times it's weight into
                    # the _default distribution table
                    for i in range(member.weight):
                        dist_tables['_default']['rotation'].append(member.ip)

                    # increase the number of unique addresses
                    # in the _default by 1
                    dist_tables['_default']['num_unique_addrs'] += 1

        ##################################
        ### post tables creation tasks ###
        ##################################
        for name in dist_tables:
            # randomly shuffle the rotation list
            random.shuffle(dist_tables[name]['rotation'])

            # create index used by ppdns for distribution,
            # set it to a random position, when ppdns is
            # syncing its internal state from shared memory, indexes gets
            # reset, we want to avoid starting from 0 every time
            dist_tables[name]['index'] = \
                int(random.random() * len(dist_tables[name]['rotation']))

        obj['dist_tables'] = dist_tables

        return obj
