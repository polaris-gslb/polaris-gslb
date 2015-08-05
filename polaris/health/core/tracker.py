# -*- coding: utf-8 -*-

import logging
import time
import multiprocessing
import queue

import memcache

import polaris.config
from polaris.health import state
from .probe import Probe

LOG = logging.getLogger(__name__)
LOG.addHandler(logging.NullHandler())

# how long to wait(block) when reading from probe response queue
# non-blocking will eat 100% cpu at low message rate
PROBE_RESPONSE_QUEUE_WAIT =  0.05 # 50 ms

# how often to issue new probe requests and sync state to shared mem(but only
# if state change occurred)
SCAN_STATE_INTERVAL = 1 # 1s

class Tracker(multiprocessing.Process):

    """Track the health status of backend servers and propagate it to 
    shared memory.
    """

    def __init__(self, probe_request_queue, probe_response_queue):
        """
        args:
            probe_request_queue: multiprocessing.Queue(), 
                queue to put new probes on
            probe_response_queue: multiprocessing.Queue(),
                queue to get processed probes from

        """    
        super(Tracker, self).__init__()

        self.probe_request_queue = probe_request_queue
        self.probe_response_queue = probe_response_queue

        # create health state table from the lb config
        self._state = state.State(config_obj=polaris.config.lb)

        # init shared memory client
        self._sm = memcache.Client(
            [polaris.config.shared_mem['hostname']])

    def run(self):
        """Main execution loop"""

        # init last_scan_state_time so we know when to run the first scan
        last_scan_state_time = time.time()

        # Track whether status of any of the backend servers changed.
        # If the state has changed we will push it to share _mem, but no more
        # often than SCAN_STATE_INTERVAL
        self._state_changed = False

        while True:
            # read probe response and process it
            try:
                # block with a small timeout,
                # non-blocking will load cpu needlessly
                probe = self.probe_response_queue.get(
                    True, PROBE_RESPONSE_QUEUE_WAIT)
            except queue.Empty: # nothing on the queue
                pass
            else:
                self._process_probe(probe)

            # periodically iterate the state and issue new probe requests,
            # if there was a state change in the last SCAN_STATE_INTERVAL,
            # push it to shared mem
            if time.time() - last_scan_state_time > SCAN_STATE_INTERVAL:
                # update last scan state time
                last_scan_state_time = time.time()

                # if the state changed, push it's distribution representation 
                # to the shared memory
                if self._state_changed:
                    # push state
                    self._sm.set(
                        polaris.config.shared_mem['health_state_key'], 
                        self._state.to_dist_dict())

                    # reset state changed flag
                    self._state_changed = False

                    LOG.debug('synced state, version to the shared memory')
 
                # iterate the state, issue new probe requests
                self._scan_state()
 
    def _process_probe(self, probe):
        """Process a probe, change the associated member status accordingly.
        
        args:
            probe: Probe() object

        """
        LOG.debug('received {}'.format(str(probe)))  

        # get a reference to the individual pool member 
        # based on pool_name and member_ip
        member = self._state.pools[probe.pool_name].members[probe.member_ip]    

        ### probe success ###
        if probe.status:
            # if member is in UP state, do nothing and return
            if member.status is True:
                return

            # member is either in DOWN state or a new member, bring it UP
            else:
                member.status = True
                # set retries left to the value of the parent's pool 
                # monitor retries
                member.retries_left = \
                    self._state.pools[probe.pool_name].monitor.retries

        ### probe failed ###
        else:
            # either a new member or a member is UP state
            if member.status is True or member.status is None:
                # more retries left?
                if member.retries_left > 0:
                    # decrease the number of retries left by 1 and return
                    member.retries_left -= 1
                    return

                # out of retries, change state to DOWN
                else:
                    member.status = False

            # member status is False, do nothing and return
            else:
                return

        # if we end up here, it means that there was a status change,
        # indicate that the overall state changed
        self._state_changed = True
        LOG.info('member "{}"({}) of pool "{}" is {} on probe, reason "{}"'
                 .format(probe.member_ip, member.name, probe.pool_name, 
                         state.pool.pprint_status(member.status),
                         probe.status_reason))
        # check if this change affects the overall pool's status
        # and generate a log message if it does
        self._change_pool_last_status(self._state.pools[probe.pool_name])

    def _scan_state(self):
        """Iterate over the health table, request health probes"""
        for pool_name in self._state.pools:
            pool = self._state.pools[pool_name]
            for member_ip in pool.members:
                member = pool.members[member_ip]

                # request probe if required
                self._request_probe(pool, member)

    def _request_probe(self, pool, member):
        """Request a probe if required (either the first probe
        or if it's time for a next one)
        """     
        request_probe = False

        # if member.last_probe_issued_time is not None, it means that
        # a probe had been issued for this member already,
        # check if it's time for a new one
        if member.last_probe_issued_time is not None: 
             if time.time() - member.last_probe_issued_time \
                    >= pool.monitor.interval:
                request_probe = True

        # else this is the first time we're issuing a probe
        # set member.retries_left to the parent's pool monitor retries
        else:
            member.retries_left = pool.monitor.retries
            request_probe = True

        if request_probe:
            # issue probe
            probe = Probe(pool_name=pool.name,
                          member_ip=member.ip,
                          monitor=pool.monitor)
            self.probe_request_queue.put(probe) 
            # update the time when the probe was issued
            member.last_probe_issued_time = time.time()
        
            LOG.debug('requested {}'.format(str(probe)))

    def _change_pool_last_status(self, pool):
        """Compare pool.last_status with pool.status, if different 
        pool.last_status is set to pool.status and a log message is generated.
        """
        if pool.last_status != pool.status:
            LOG.info('pool "{}" status changed to {}'.
                     format(pool.name, state.pool.pprint_status(pool.status))) 
            pool.last_status = pool.status

