# -*- coding: utf-8 -*-

import time
import json

import memcache

from polaris_health.util import topology

from polaris_pdns import config
from .remotebackend import RemoteBackend

__all__ = [ 'Polaris' ]

# minimum number of seconds between syncing distribution state from shared mem 
STATE_SYNC_INTERVAL = 1

class Polaris(RemoteBackend):
    
    """Polaris PDNS remote backend.

    Distribute queries according to the distribution state and the load
    balancing method.
    """
    
    def __init__(self):
        super(Polaris, self).__init__()

        # shared memory client
        self._sm = memcache.Client([config.BASE['SHARED_MEM_HOSTNAME']])   
       
        # this will hold the distribution state
        self._state = {}

        # used to determine whether we need to set self._state
        # to the state we pull from shared memory(every STATE_SYNC_INTERVAL)
        # initialize with 0 as it will be used for comparison
        # in self._sync_state on it's first run
        self._state_timestamp = 0

        # time when the state was last synced from shared memory
        # init with 0 for comparison in _sync_state() to work 
        self._state_last_synced = 0

    def do_lookup(self, params):
        """
        args:
            params: 'parameters' dict from PowerDNS JSON API request
        
        """
        # sync(if required) state from the shared memory
        self._sync_state()

        # respond with False if there is no globalname corresponding
        # to the qname, this will result in REFUSED in the front-end
        if params['qname'].lower() not in self._state['globalnames']:
            self.log.append(
                'no globalname found for qname "{}"'.format(params['qname']))
            self.result = False
            return

        # ANY/A response
        if params['qtype'] == 'ANY' or params['qtype'] == 'A':
            self._any_response(params)
            return

        # SOA response
        if params['qtype'] == 'SOA':
            self._soa_response(params)
            return

        # REFUSE otherwise
        self.result = False

    def do_getDomainMetadata(self, params):
        """PDNS seems to ask for this quite a bit,
        respond with result:false

        """
        self.result = False

    def _any_response(self, params):
        """Generate a response to ANY/A query

        See polaris_health.state to_dist_dict() methods for the distribution
        state implementation details.

        """
        qname = params['qname'].lower()

        # get a pool associated with the qname
        pool_name = self._state['globalnames'][qname]['pool_name']
        pool = self._state['pools'][pool_name]
       
        # use the _default distribution table by default
        dist_table = pool['dist_tables']['_default']

        ##################
        ### pool is UP ###
        ##################
        if pool['status']:
            # if using a topology based method, check if we have a distribution
            # table in the same region, if so - use it
            if pool['lb_method'] == 'twrr':

                # we'll log the time it takes to perfom a topology lookup
                t = time.time()

                # lookup the client's region, get_region() will
                # return None if the region cannot be determined
                region = topology.get_region(params['remote'], 
                                             config.TOPOLOGY_MAP)

                # log the time taken to perform the lookup
                self.log.append(
                    'get_region() time taken: {:.6f}'.format(time.time() - t))

                # log client's region
                self.log.append('client region: {}'.format(region))

                # if we have a region table corresponding 
                # to the client's region - use it
                if region in pool['dist_tables']:
                    dist_table = pool['dist_tables'][region]

        ####################
        ### pool is DOWN ###
        ####################
        else:
            # if fallback is set to "refuse", refuse the query
            # (SOA response must return False as well)
            if pool['fallback'] == 'refuse':
                self.result = False
                return

            # otherwise(fallback is "any") use the _default distribution table

        # log the distribution table used
        self.log.append('dist table used: {}'
                        .format(json.dumps(dist_table)))

        # determine how many records to return
        # which is the minimum of the dist table's num_unique_addrs and 
        # the pool's max_addrs_returned
        if dist_table['num_unique_addrs'] <= pool['max_addrs_returned']: 
            num_records_return = dist_table['num_unique_addrs']
        else:    
            num_records_return = pool['max_addrs_returned']

        # if we don't have anything to return(all member weights may have
        # been set of 0), set the result to false
        if num_records_return == 0:
            self.result = False
            return

        ### add records to the response ###
        for i in range(num_records_return):
            # add record to the response
            self.add_record(qtype='A',
                            # use the original qname from the parameters dict        
                            qname=params['qname'],
                            content=dist_table['rotation'][dist_table['index']],
                            ttl=self._state['globalnames'][qname]['ttl'])    

            # increase index
            dist_table['index'] += 1
            # set the index to 0 if we reached the end of the rotation list
            if dist_table['index'] >= len(dist_table['rotation']):
                dist_table['index'] = 0

    def _soa_response(self, params):
        """Generate a response to a SOA query

        """
        # if pool is DOWN and fallback is set to "refuse", refuse SOA queries
        # when both SOA any ANY results in False the pdns will produce a REFUSE
        qname = params['qname'].lower()
        pool_name = self._state['globalnames'][qname]['pool_name']
        pool = self._state['pools'][pool_name]
        if not pool['status'] and pool['fallback'] == 'refuse':
            self.result = False
            return

        # append ns with a dot here
        ns = '{}.'.format(config.BASE['HOSTNAME'])
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
        """Synchronize the local distribution state from shared memory

        """
        t = time.time()

        # do not sync state if STATE_SYNC_INTERVAL seconds haven't passed
        # since the last sync
        if t - self._state_last_synced < STATE_SYNC_INTERVAL:
            return

        # get the distribution state object from shared memory
        sm_state = self._sm.get(config.BASE['SHARED_MEM_PPDNS_STATE_KEY'])

        # check timestamp on it, if it did not change since the last pull
        # do not update the local memory state to avoid resetting
        # rotation indexes needlessly
        if self._state_timestamp == sm_state['timestamp']:
            return

        # otherwise make the shared memory state fetched the self._state
        self._state = sm_state

        # update self._state_timestamp
        self._state_timestamp = sm_state['timestamp']

        # update _state_last_synced
        self._state_last_synced = t

