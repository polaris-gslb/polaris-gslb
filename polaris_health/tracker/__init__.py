# -*- coding: utf-8 -*-

import logging
import time
import multiprocessing
import threading
import queue

import memcache

from polaris_common import sharedmem
from polaris_health import config, state, util
from polaris_health.prober.probe import Probe


LOG = logging.getLogger(__name__)
LOG.addHandler(logging.NullHandler())

# how long to wait(block) when reading from probe response queue
# non-blocking will eat 100% cpu at low message rate
PROBE_RESPONSES_QUEUE_WAIT =  0.050

# how often to scan the state(and issue probe requests)
SCAN_STATE_INTERVAL = 1 # 1s

# the main load balancing state, initialized in Tracker's init
STATE = None
# lock synchronizing access to the STATE between Tracker and StatePusher
STATE_LOCK = threading.Lock()
# state timestamp is changed whenever a pool member state changes,
# this in turn used by StatePusher to determine whether it needs 
# to push state into shared memory
STATE_TIMESTAMP = 0
# how long to sleep after a state push before attempting a new push
STATE_PUSH_INTERVAL = 0.5


class StatePusher(threading.Thread):
    
    """StatePusher pushes state updates into shared memory.
    """

    def __init__(self):
        super(StatePusher, self).__init__()

        # flag the thread as daemon so it's abruptly killed
        # when its parent process exists
        self.daemon = True

        # shared memory client
        self.sm = sharedmem.MemcacheClient(
            [config.BASE['SHARED_MEM_HOSTNAME']],
            socket_timeout=config.BASE['SHARED_MEM_SOCKET_TIMEOUT'],
            server_max_value_length=config.BASE['SHARED_MEM_SERVER_MAX_VALUE_LENGTH'])

        # on startup do not attempt to push state
        self.state_ts = 0

    def run(self):
        while True:
            # initial values of states_ts should be set  to 0
            # so we don't attempt a state push until STATE_TIMESTAMP changes
            if STATE_TIMESTAMP != self.state_ts:
                self.push_states()
            # sleep until the next iteration    
            time.sleep(STATE_PUSH_INTERVAL)

    def push_states(self): 
        # lock the state and generate its various forms
        global STATE_LOCK
        with STATE_LOCK:
            # generate ppdns distribution form of the state
            dist_form = STATE.to_dist_dict()
            # generate generic form of the state
            generic_form = util.instance_to_dict(STATE)

        # all memcache pushes must succeed in order to
        # reset state changed flag
        pushes_ok = 0

        # push PPDNS distribution form of the state
        val = self.sm.set(config.BASE['SHARED_MEM_PPDNS_STATE_KEY'],
                           dist_form)
        if val is True:
            pushes_ok += 1
        else:    
            log_msg = ('failed to write ppdns state to the shared memory')
            LOG.warning(log_msg)

        # push generic form of the state
        # add timestampt to the object
        generic_form['timestamp'] = STATE_TIMESTAMP
        val = self.sm.set(config.BASE['SHARED_MEM_GENERIC_STATE_KEY'],
                           generic_form)
        if val is True:
            pushes_ok += 1
        else:
            log_msg = ('failed to write generic state to the shared memory')
            LOG.warning(log_msg)

        # push state timestamp last
        val = self.sm.set(config.BASE['SHARED_MEM_STATE_TIMESTAMP_KEY'],
                           STATE_TIMESTAMP)
        if val is True:
            pushes_ok += 1
        else:    
            log_msg = ('failed to write state timestamp to the shared memory')
            LOG.warning(log_msg)

        # if all memcache pushes are successful
        # set self.state_ts to STATE_TIMESTAMP so we don't attempt to
        # push again until STATE_TIMESTAMP changes
        if pushes_ok == 3:
            LOG.debug('synced state to the shared memory')
            self.state_ts = STATE_TIMESTAMP


class Tracker(multiprocessing.Process):

    """Track the health status of backend servers and propagate it to 
    shared memory.
    """

    def __init__(self, prober_requests, prober_responses):
        """
        args:
            prober_requests: multiprocessing.Queue(), 
                queue to put new probes on
            prober_responses: multiprocessing.Queue(),
                queue to get processed probes from
        """
        super(Tracker, self).__init__()

        self.prober_requests = prober_requests
        self.prober_responses = prober_responses

        # create health state table from the lb config
        global STATE
        STATE = state.State(config_obj=config.LB)

    def run(self):
        """Main scheduling/processing loop"""

        # start StatePusher thread
        # must be started from here, not __init__, in order for 
        # global variables to be seen across both tracker and pusher
        StatePusher().start()

        # run the first scan as soon as we start
        last_scan_state_time = 0

        global STATE_LOCK
        while True:
            # read probe response and process it
            try:
                # block with a small timeout,
                # non-blocking will load cpu needlessly
                probe = self.prober_responses.get(
                    block=True, timeout=PROBE_RESPONSES_QUEUE_WAIT)
            except queue.Empty: # nothing on the queue
                pass
            else:
                with STATE_LOCK:
                    self._process_probe(probe)

            # periodically iterate the state and issue new probe requests,
            # if there was a state change in the last SCAN_STATE_INTERVAL,
            # push it to shared mem
            if time.time() - last_scan_state_time > SCAN_STATE_INTERVAL:
                # update last scan state time
                last_scan_state_time = time.time()

                # iterate the state, issue new probe requests
                with STATE_LOCK:
                    self._scan_state()

    def _process_probe(self, probe):
        """Process probe, change the associated member status accordingly.
        
        args:
            probe: Probe() object
        """
        LOG.debug('received {}'.format(str(probe)))  

        # get a reference to the individual pool member 
        # based on pool_name and member_ip
        for member in STATE.pools[probe.pool_name].members:
            if member.ip == probe.member_ip:
                break

        # set member status attributes 
        member.status_reason = probe.status_reason
        
        ### probe success ###
        if probe.status:
            # reset the value of retries left to the parent's pool value
            member.retries_left = \
                STATE.pools[probe.pool_name].monitor.retries

            # if member is in UP state, do nothing and return
            if member.status is True:
                return

            # member is either in DOWN state or a new member, bring it UP
            else:
                member.status = True

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
        # indicate this to State Pusher by updating global STATE_TIMESTAMP
        global STATE_TIMESTAMP
        STATE_TIMESTAMP = time.time()

        LOG.info('pool member status change: '
                'member {member_ip}'
                '(name: {member_name} monitor IP: {monitor_ip}) '
                'of pool {pool_name} is {member_status}, '
                'reason: {member_status_reason}'
                 .format(member_ip=probe.member_ip,
                         member_name=member.name,
                         monitor_ip=member.monitor_ip,
                         pool_name=probe.pool_name, 
                         member_status=state.pool.pprint_status(member.status),
                         member_status_reason=member.status_reason))
        # check if this change affects the overall pool's status
        # and generate a log message if it does
        self._change_pool_last_status(STATE.pools[probe.pool_name])

    def _scan_state(self):
        """Iterate over the state, request health probes"""
        for pool_name in STATE.pools:
            pool = STATE.pools[pool_name]
            for member in pool.members:
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
                          monitor=pool.monitor,
                          monitor_ip=member.monitor_ip)

            self.prober_requests.put(probe) 

            # update the time when the probe was issued
            member.last_probe_issued_time = time.time()
        
            #LOG.debug('requested {}'.format(str(probe)))

    def _change_pool_last_status(self, pool):
        """Compare pool.last_status with pool.status, if different 
        pool.last_status is set to pool.status and a log message is generated.
        """
        if pool.last_status != pool.status:
            LOG.info('pool status change: pool {} is {}'.
                     format(pool.name, state.pool.pprint_status(pool.status))) 
            pool.last_status = pool.status

