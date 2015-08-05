# -*- coding: utf-8 -*-

import time
import json

import memcache

import polaris
import polaris.util.topology
from .pdns import RemoteBackend

__all__ = [ 'Distributor' ]

# minimum time in seconds between distribution state sync from shared mem 
STATE_SYNC_INTERVAL = 1

class Distributor(RemoteBackend):
    
    """Distribute queries according to the distribution state and the load
    balancing method.
    """
    
    def __init__(self):
        super(Distributor, self).__init__()

        # shared memory client
        self._sm = memcache.Client(
            [polaris.config.shared_mem['hostname']])   
       
        # this will hold the distribution state
        self._state = {}

        # used to determine whether we need to set self._state
        # to the state we pull from shared memory(every STATE_SYNC_INTERVAL)
        # initialize with a value as it will be used for comparison
        # in self._sync_state on it's first run
        self._state_timestamp = 0

        # timestap when the state was last synced from shared memory
        # init with 0 for comparison in _sync_state() to work 
        self._state_last_synced = 0

    def do_lookup(self, params):
        """
        args:
            params: 'parameters' dict from PowerDNS JSON API request
        """
        # sync state from shared memory
        self._sync_state()

        # respond with False if there is no globalname corresponding
        # to the qname, this will result in REFUSED at the front-end
        if params['qname'].lower() not in self._state['globalnames']:
            self.log.append(
                'error: no globalname for qname "{}"'.format(params['qname']))
            self.result = False
            return

        # SOA response
        if params['qtype'] == 'SOA':
            self._soa_response(params)
            return

        # ANY/A response
        if params['qtype'] == 'ANY' or params['qtype'] == 'A':
            self._any_response(params)
            return

        # drop otherwise
        self.result = False

    def do_getDomainMetadata(self, params):
        """Always respond with {"result": ["NO"]}"""
        self.result =  [ 'NO' ]

    def _any_response(self, params):
        """Generate a response to ANY/A query"""

        qname = params['qname'].lower()

        # get pool associated with the qname
        pool_name = self._state['globalnames'][qname]['pool_name']
        pool = self._state['pools'][pool_name]
       
        # if using a topology based method, get client's region
        # get_region() will return None if the region cannot be determined
        if pool['lb_method'] == 'twrr':
            t = time.time()
            region = polaris.util.topology.get_region(params['remote'])
            self.log.append('client_region: {}'.format(region))
            self.log.append(
                'polaris.get_region_time_taken: {:.6f}'.format(time.time() - t))

        # determine which dist table to use
        # use _default table by default
        dist_table = pool['dist_tables']['_default']

        # if using a topology method, have a region table corresponding to 
        # the client's region and it's not empty, use it
        if pool['lb_method'] == 'twrr':
            if region in pool['dist_tables'] and \
                    pool['dist_tables'][region]['rotation']:
                dist_table = pool['dist_tables'][region]

        # expose distribution table used in the log
        self.log.append('dist_table_used: {}'.format(json.dumps(dist_table)))

        # determine how many records to return, which is
        # the minimum of the dist table's num_unique_addrs and 
        # the pool's max_addrs_returned
        if dist_table['num_unique_addrs'] <= pool['max_addrs_returned']: 
            num_records_return = dist_table['num_unique_addrs']
        else:    
            num_records_return = pool['max_addrs_returned']

        # add records to the response    
        for i in range(num_records_return):
            # add record to the response
            self.add_record(qtype='A',
                            # use the original qname from the parameters dict        
                            qname=params['qname'],
                            content=dist_table['rotation'][dist_table['index']],
                            ttl=self._state['globalnames'][qname]['ttl'])    

            # increase index, set it to 0 if we reached 
            # the end of the rotation list
            dist_table['index'] += 1
            if dist_table['index'] >= len(dist_table['rotation']):
                dist_table['index'] = 0

    def _soa_response(self, params):
        """Generate a response to SOA query"""

        # append ns with a dot here
        ns = '{}.'.format(polaris.config.base['distributor']['hostname'])
        contact = 'hostmaster.{}'.format(ns)                   
        content = ('{ns} {contact} {serial} {retry} {expire} {min_ttl}'.
                   format(ns=ns,
                          contact=contact,
                          serial=1,
                          retry=600,
                          expire=86400,
                          min_ttl=1))

        # add record to the response
        self.add_record(qtype='SOA',
                        # use the original qname from parameters dict
                        qname=params['qname'],
                        content=content,
                        ttl=60)

    def _sync_state(self):
        """Synchronize local distribution state from shared memory"""

        t = time.time()
        # do not sync state if STATE_SYNC_INTERVAL seconds haven't passed
        # since the last sync
        if t - self._state_last_synced < STATE_SYNC_INTERVAL:
            return

        # get the distribution state object from shared memory
        sm_state = self._sm.get(
            polaris.config.shared_mem['health_state_key'])

        # check timestamp on it, if it did not change since the last pull
        # do not update the local memory state to avoid resetting
        # rotation indexes needlessly
        if self._state_timestamp == sm_state['timestamp']:
            return

        # otherwise make the shared memory state fetched the self._state
        self._state = self._sm.get(
            polaris.config.shared_mem['health_state_key'])

        # update self._state_timestamp
        self._state_timestamp = sm_state['timestamp']

        # update _state_last_synced
        self._state_last_synced = t

