# -*- coding: utf-8 -*-

__all__ = [ 
    'BASE',
    'LB',
    'TOPOLOGY_MAP'
]

BASE = {
    # can be overriden by configuration file
    'SHARED_MEM_HOSTNAME': '127.0.0.1',
    'SHARED_MEM_GENERIC_STATE_KEY': 'polaris_health:generic_state',
    'SHARED_MEM_PPDNS_STATE_KEY': 'polaris_health:ppdns_state',
    'SHARED_MEM_HEARTBEAT_KEY': 'polaris_health:heartbeat',

    'NUM_PROBERS': 2,

    'LOG_LEVEL': 'info',
    'LOG_HANDLER': 'syslog',
    'LOG_HOSTNAME': '127.0.0.1',
    'LOG_PORT': 2222,

    # copied from POLARIS_INSTALL_PREFIX env
    'INSTALL_PREFIX': None,

    # hard set based on INSTALL_PREFIX
    'PID_FILE': None,
    'CONTROL_SOCKET_FILE': None,
}

LB = {}

TOPOLOGY_MAP = {}

