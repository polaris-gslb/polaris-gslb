# -*- coding: utf-8 -*-

import logging
import ipaddress

import yaml

from polaris import Error

__all__ = [ 
    'base',
    'lb',
    'topology', 
    'load'         
]

LOG = logging.getLogger(__name__)
LOG.addHandler(logging.NullHandler())

# shared memory 
shared_mem = {
    'hostname': '127.0.0.1', 
    'health_state_key': 'polaris:health:state',
    'health_heartbeat_key': 'polaris:health:heartbeat',    
}

base = {}
lb = {}
topology = {}

def load(base_config_path=None, lb_config_path=None, topology_config_path=None):
    """Load configuration based on the provided file paths. 
    It's possible to only load a specific part of the configuration, 
    e.g. topology, in order to perform configuration validation from external 
    applications.

    args:
        base_config_path: string, full path to base.yaml
        lb_config_path: string, full path to lb.yaml
        topology_config_path: string, full path to topology.yaml
    """
    global base, lb, topology

    if base_config_path:
        with open(base_config_path) as fp:
            base = yaml.load(fp)

    if lb_config_path:
        with open(lb_config_path) as fp:
            lb = yaml.load(fp)

    if topology_config_path:
        with open(topology_config_path) as fp:
            topology_config = yaml.load(fp)

        # convert topology config into topology map dict:
        # {
        #   ipaddress.IPNetwork: region,
        # }
        for region in topology_config:
            # "_default" cannot be used as a region name
            if region == '_default':
                raise Error('"_default" is a system-reserved region name')

            for net_str in topology_config[region]:
                net = ipaddress.ip_network(net_str)
                topology[net] = region

