# -*- coding: utf-8 -*-
import logging
import time
import multiprocessing
import threading
import queue
import heapq

import memcache

from polaris_common import sharedmem
from polaris_health import config, state, util
from polaris_health.prober.probe import Probe


LOG = logging.getLogger(__name__)
LOG.addHandler(logging.NullHandler())

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
# how long to idle if there is no work currently to avoid a tight loop
DO_IDLE_DURATION = 0.05

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

        # on startup state_ts == STATE_TIMESTAMP == 0
        self.state_ts = 0

    def run(self):
        while True:
            # push the states whenever STATE_TIMESTAMP changes
            # (but only after the health status has fully converged)
            if STATE_TIMESTAMP != self.state_ts:
                self.push_states()
            # sleep until the next iteration    
            time.sleep(STATE_PUSH_INTERVAL)

    def push_states(self): 
        # lock the state and generate its various forms
        global STATE_LOCK
        with STATE_LOCK:
            # do not push states until every member's health status
            # has been determined
            if not STATE.health_converged:
                return

            # generate ppdns distribution form of the state
            dist_form = STATE.to_dist_dict()
            # generate generic form of the state
            generic_form = util.instance_to_dict(STATE, ignore_private=True)

        # all memcache pushes must succeed in order to
        # update the state pushed flag(self.state_ts)
        pushes_ok = 0

        # push PPDNS distribution form of the state
        val = self.sm.set(config.BASE['SHARED_MEM_PPDNS_STATE_KEY'],
                          dist_form)
        if val is True:
            pushes_ok += 1
        else:    
            log_msg = ('failed to write ppdns state to the shared memory')
            LOG.error(log_msg)

        # push generic form of the state
        # add timestampt to the object
        generic_form['timestamp'] = STATE_TIMESTAMP
        val = self.sm.set(config.BASE['SHARED_MEM_GENERIC_STATE_KEY'],
                          generic_form)
        if val is True:
            pushes_ok += 1
        else:
            log_msg = ('failed to write generic state to the shared memory')
            LOG.error(log_msg)

        # push state timestamp last
        val = self.sm.set(config.BASE['SHARED_MEM_STATE_TIMESTAMP_KEY'],
                          STATE_TIMESTAMP)
        if val is True:
            pushes_ok += 1
        else:    
            log_msg = ('failed to write state timestamp to the shared memory')
            LOG.error(log_msg)

        # if all memcache pushes are successful
        # set self.state_ts to STATE_TIMESTAMP so we don't attempt to
        # push again until STATE_TIMESTAMP changes
        if pushes_ok == 3:
            LOG.debug('synced state to the shared memory')
            self.state_ts = STATE_TIMESTAMP


class Tracker(multiprocessing.Process):

    """Track the health status of backend servers and propagate it to 
    the shared memory.
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
        """Scheduling/receiving loop"""
        # start StatePusher thread
        # must be started from here, not __init__, in order for 
        # global variables to be seen across both tracker and pusher
        StatePusher().start()

        global STATE_LOCK
        while True:
            # if we neither have a probe response to process
            # nor a next probe to issue - we'll idle for a short 
            # time to avoid a tight loop
            do_idle = True
            
            # read the next probe response and process it
            try:
                # non-blocking queue get
                probe_response = self.prober_responses.get(block=False)
            except queue.Empty: # nothing on the queue
                pass
            else:
                with STATE_LOCK:
                    self._process_probe_response(probe_response)
                    do_idle = False

            # read the top of the queue and see if we need to issue a probe,
            # priority valuer is the monotime of when the probe needs to run
            if time.monotonic() - STATE._pq[0][0] >= 0:
                do_idle = False
                with STATE_LOCK:
                    # shortcuts to pool, member
                    pool = STATE._pool_by_id[STATE._pq[0][1].pool_id]
                    member = STATE._member_by_id[STATE._pq[0][1].member_id]
                    
                    # determine when to run this probe next time
                    next_probe_monotime = \
                        time.monotonic() + pool.monitor.interval
                    
                    # insert a new item into the pq, removing
                    # the top item at the same time
                    heapq.heapreplace(
                        STATE._pq,
                        (next_probe_monotime, # priority
                        state.PQItem(pool_id=pool._id, member_id=member._id)))
                    
                    # issue the probe request
                    self._issue_probe_request(pool=pool,
                                              member=member)

            # idle for a bit if we had no work to do to void a tight loop
            if do_idle:
                time.sleep(DO_IDLE_DURATION)

    def _issue_probe_request(self, pool, member):
        """Issue a probe request.
        """ 
        # create a new Probe object
        probe_request = Probe(
            pool_id=pool._id,
            pool_name=pool.name,
            member_id=member._id,
            member_ip=member.ip,
            monitor=pool.monitor,
            monitor_ip=member.monitor_ip)

        # send it to the requests queue
        self.prober_requests.put(probe_request) 
  
        #LOG.debug('requested {}'.format(str(probe_request)))

    def _process_probe_response(self, probe_response):
        """Process the probe response and change the state accordingly.
        
        args:
            probe: prober.Probe object
        """
        LOG.debug('received {}'.format(str(probe_response)))  

        # pool, member shortcuts
        pool = STATE._pool_by_id[probe_response.pool_id]
        member = STATE._member_by_id[probe_response.member_id]

        # set the member's status attributes 
        member.status_reason = probe_response.status_reason
        
        ### probe succeeded ###
        if probe_response.status:
            # reset the value of retries left to the parent pool's retries 
            member.retries_left = pool.monitor.retries

            # if member is in UP state, do nothing and return
            if member.status is True:
                return

            # member is either DOWN or not initialized, bring it UP
            else:
                member.status = True

        ### probe failed ###
        else:
            # member is either UP or not initialized 
            if member.status is True or member.status is None:
                # more retries left?
                if member.retries_left > 0:
                    # decrease the number of retries left by 1 and return
                    member.retries_left -= 1
                    return

                # out of retries, change the status to DOWN
                else:
                    member.status = False

            # member is already DOWN, do nothing and return
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
                 .format(member_ip=member.ip,
                         member_name=member.name,
                         monitor_ip=member.monitor_ip,
                         pool_name=pool.name, 
                         member_status=state.pool.pprint_status(member.status),
                         member_status_reason=member.status_reason))
        
        # check if this change affects the overall pool's status
        # and generate a log message if it does
        if pool.last_status != pool.status:
            LOG.info('pool status change: pool {} is {}'.
                     format(pool.name, state.pool.pprint_status(pool.status)))
            pool.last_status = pool.status
