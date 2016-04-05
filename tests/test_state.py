# -*- coding: utf-8 -*-

import sys
import os
import inspect 
import json

import pytest

path = os.path.abspath(
    os.path.split(inspect.getfile( inspect.currentframe() ))[0])
sys.path.insert(0, os.path.split(path)[0])

from polaris_health import util, runtime, state


def to_pretty_json(obj):
    """Encode to pretty-looking JSON string"""
    return json.dumps(obj, sort_keys=False, 
                      indent=4, separators=(',', ': '))


def get_lb_cfg_dict():
    config = {
        'pools': {
            'test-pool1': {
                'monitor': 'tcp',
                'monitor_params': {
                    'port': 123
                },
                'lb_method': 'wrr',
                'fallback': 'any',
                'members': [
                    {
                        'ip': '10.1.1.1',
                        'name': 'server1',
                        'weight': 1,
                    },

                    {
                        'ip': '10.1.2.1',
                        'name': 'server2',
                        'weight': 1,
                    },

                    {
                        'ip': '10.1.3.1',
                        'name': 'server3',
                        'weight': 1
                    },
                ]
            },
        },

        'globalnames': {
            'www.test.org': {
                'pool': 'test-pool1',
                'ttl': 1
            }
        },
    }
    return config


class TestDistributionState:

    def print_state(self):
        print('state:')
        print(to_pretty_json(util.instance_to_dict(self.state)))

    def print_dist_dict(self):
        print('distribution dict:')
        print(to_pretty_json(self.state.to_dist_dict()))

    def pool_status(self, pool_name):
        return self.state.to_dist_dict()['pools'][pool_name]['status']

    def rotation_set(self, pool_name, table_name):
        return  set(self.state.to_dist_dict()['pools'][pool_name][
            'dist_tables'][table_name]['rotation'])

    def test_lb_method_fogroup(self):
        ### fallback ANY ###
        cfg_dict = get_lb_cfg_dict()
        cfg_dict['pools']['test-pool1']['lb_method'] = 'fogroup'
        cfg_dict['pools']['test-pool1']['fallback'] = 'any'
        self.state = state.State(cfg_dict)   

        # all members down
        assert self.pool_status('test-pool1') == False
        assert self.rotation_set('test-pool1', '_default') == \
            set(['10.1.1.1', '10.1.2.1','10.1.3.1'])

        # all up
        for member in self.state.pools['test-pool1'].members:
            member.status = True
        assert self.pool_status('test-pool1') == True
        assert self.rotation_set('test-pool1', '_default') == \
            set(['10.1.1.1'])

        # first member down
        self.state.pools['test-pool1'].members[0].status = False
        assert self.pool_status('test-pool1') == True
        assert self.rotation_set('test-pool1', '_default') == \
            set(['10.1.2.1'])

        # first and second members down
        self.state.pools['test-pool1'].members[1].status = False
        assert self.pool_status('test-pool1') == True
        assert self.rotation_set('test-pool1', '_default') == \
            set(['10.1.3.1'])

        ### fallback REFUSE ###
        cfg_dict = get_lb_cfg_dict()
        cfg_dict['pools']['test-pool1']['lb_method'] = 'fogroup'
        cfg_dict['pools']['test-pool1']['fallback'] = 'refuse'
        self.state = state.State(cfg_dict) 

        # all members down
        assert self.pool_status('test-pool1') == False
        assert self.rotation_set('test-pool1', '_default') == \
            set([])

        # first member up
        self.state.pools['test-pool1'].members[0].status = True
        assert self.pool_status('test-pool1') == True
        assert self.rotation_set('test-pool1', '_default') == \
            set(['10.1.1.1'])

        # first an second members up
        self.state.pools['test-pool1'].members[1].status = True
        assert self.pool_status('test-pool1') == True
        assert self.rotation_set('test-pool1', '_default') == \
            set(['10.1.1.1'])

        # all up
        self.state.pools['test-pool1'].members[2].status = True
        assert self.pool_status('test-pool1') == True
        assert self.rotation_set('test-pool1', '_default') == \
            set(['10.1.1.1'])


