# -*- coding: utf-8 -*-

import time
import json
import threading 

import memcache

from polaris_common import topology, sharedmem
from polaris_pdns import config
from .remotebackend import RemoteBackend


__all__ = [ 'Polaris' ]

# distribution state
STATE = {}
# timestamp of the state
STATE_TS = 0
# lock for both STATE, STATE_TS sync between Polaris() and StateUpdater() 
STATE_LOCK = threading.Lock() 
# how long to sleep after attempting a state update
STATE_UPDATE_INTERVAL = 0.5


class StateUpdater(threading.Thread):
    
    """StateUpdater updates the global distribution state from shared memory
    on a predefined interval.
    State timestamp only is fetched first, compared to the current timestamp 
    and, if different, full state if fetched and made active.
    """

    def __init__(self):
        super(StateUpdater, self).__init__()

        # flag the thread as daemon so it's abruptly killed
        # when its parent process exists
        self.daemon = True

        # shared memory client
        self.sm = sharedmem.MemcacheClient(
            [config.BASE['SHARED_MEM_HOSTNAME']],
            socket_timeout=config.BASE['SHARED_MEM_SOCKET_TIMEOUT'])

    def run(self):
        while True:
            # attempt to update state as soon as we start
            self.update_state()
            time.sleep(STATE_UPDATE_INTERVAL)

    def update_state(self):     
        # fetch state timestamp
        state_ts = self.sm.get(config.BASE['SHARED_MEM_STATE_TIMESTAMP_KEY'])

        # failed ot fetch the timestamp, do nothing
        if state_ts is None:
            return

        global STATE_TS
        # if the fetched timestamp is the same as the current timestamp do nothing
        if state_ts == STATE_TS:
            return

        # get distribution form of state from shared memory
        state = self.sm.get(config.BASE['SHARED_MEM_PPDNS_STATE_KEY'])

        # failed ot fetch the state, do nothing
        if state is None:
            return

        # update STATE, STATE_TS
        global STATE, STATE_LOCK

        with STATE_LOCK:
            # point STATE to the fetched state
            STATE = state

            # update state's timestamp
            STATE_TS = state_ts


class Polaris(RemoteBackend):
    
    """Polaris PDNS remote backend.

    Distribute queries according to distribution state and load
    balancing method.
    """
    
    def __init__(self):
        super(Polaris, self).__init__()

    def run_additional_startup_tasks(self):
        """In order for global variables to work correctly 
        between StateUpdater and Polaris RemoteBackend,
        StateUpdater thread must be started not from __init__().
        """
        # attempt to update state once so we have a state before 
        # starting to answer queries 
        StateUpdater().update_state()

        # start the StateUpdater as a thread
        StateUpdater().start()

    def do_lookup(self, params):
        """
        args:
            params: 'parameters' dict from PowerDNS JSON API request
        """
        global STATE_LOCK
        with STATE_LOCK:
            # respond with False if there is no globalname corresponding
            # to the qname, this will result in REFUSED in the front-end
            if params['qname'].lower() not in STATE['globalnames']:
                self.log.append(
                    'no globalname found for qname "{}"'.format(params['qname']))
                self.result = False
                return

            # ANY/A response
            if params['qtype'] in ('ANY', 'A', 'AAAA'):
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
        """Generate a response to ANY/A query.

        See polaris_health.state to_dist_dict() methods for the distribution
        state implementation details.
        """
        qname = params['qname'].lower()

        # get a pool associated with the qname
        pool_name = STATE['globalnames'][qname]['pool_name']
        pool = STATE['pools'][pool_name]

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


        responses=[]
        ### add records to the response ###
        for i in range(len(dist_table['rotation'])):
            if ':' in dist_table['rotation'][dist_table['index']]:
                qtype='AAAA'
            else:
                qtype='A'
            # add record to the responses
            responses.append(
                {'qtype': qtype,
                # use the original qname from the parameters dict
                'qname': params['qname'],
                'content': dist_table['rotation'][dist_table['index']],
                'ttl': STATE['globalnames'][qname]['ttl']
                })

            # increase index
            dist_table['index'] += 1
            # set the index to 0 if we reached the end of the rotation list
            if dist_table['index'] >= len(dist_table['rotation']):
                dist_table['index'] = 0

        # TODO: remove dublicates from responses

        # sort records by type
        ip4 = [r for r in responses if r['qtype'] == 'A']
        ip6 = [r for r in responses if r['qtype'] == 'AAAA']

        # if we don't have anything to return(all member weights may have
        # been set of 0), set the result to false
        if (pool['max_addrs_returned'] == 0 or
            (params['qtype'] == 'A' and len(ip4) == 0) or
            (params['qtype'] == 'AAAA' and len(ip6) == 0) or
            len(responses) == 0):
                self.result = False
                return

        if params['qtype'] in ('ANY', 'A'):
            # determine how many records to return
            # which is the minimum of the dist table's num_unique_addrs and
            # the pool's max_addrs_returned
            if len(ip4) <= pool['max_addrs_returned']:
                num_records_return = len(ip4)
            else:
                num_records_return = pool['max_addrs_returned']

            for r in ip4[:num_records_return]:
                self.add_record(**r)

        if params['qtype'] in ('ANY', 'AAAA'):
            # determine how many records to return
            # which is the minimum of the dist table's num_unique_addrs and
            # the pool's max_addrs_returned
            if len(ip6) <= pool['max_addrs_returned']:
                num_records_return = len(ip6)
            else:
                num_records_return = pool['max_addrs_returned']

            for r in ip6[:num_records_return]:
                self.add_record(**r)

    def _soa_response(self, params):
        """Generate a response to a SOA query."""
        # if pool is DOWN and fallback is set to "refuse", refuse SOA queries
        # when both SOA any ANY results in False the pdns will produce a REFUSE
        qname = params['qname'].lower()
        pool_name = STATE['globalnames'][qname]['pool_name']
        pool = STATE['pools'][pool_name]
        if not pool['status'] and pool['fallback'] == 'refuse':
            self.result = False
            return

        # determine the value of SOA serial, 
        # either static or rounded state's timestamp
        if config.BASE['SOA_SERIAL'] == 'auto':
            serial = int(STATE_TS)
        else:
            serial = config.BASE['SOA_SERIAL']

        content = ('{mname} {rname} {serial} {refresh} {retry} {expire} {minimum}'.
                   format(mname=config.BASE['SOA_MNAME'],
                          rname=config.BASE['SOA_RNAME'],
                          serial=serial,
                          refresh=config.BASE['SOA_REFRESH'],
                          retry=config.BASE['SOA_RETRY'],
                          expire=config.BASE['SOA_EXPIRE'],
                          minimum=config.BASE['SOA_MINIMUM']))

        # add record to the response
        self.add_record(qtype='SOA',
                        # use the original qname from parameters dict
                        qname=params['qname'],
                        content=content,
                        ttl=config.BASE['SOA_TTL'])

