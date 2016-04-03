#-*- coding: utf-8 -*-

BASE = {
    # can be overriden by a configuration file
    'HOSTNAME': 'polaris.example.com',
   
    'SHARED_MEM_HOSTNAME': '127.0.0.1',
    'SHARED_MEM_PPDNS_STATE_KEY': 'polaris_health:ppdns_state',    
    'SHARED_MEM_SOCKET_TIMEOUT': 1,

    'LOG': False,

    # copied from POLARIS_INSTALL_PREFIX env when the configuration is loaded
    'INSTALL_PREFIX': None,
}

TOPOLOGY_MAP = {}

