#-*- coding: utf-8 -*-

BASE = {
    # can be overriden by a configuration file
    'SOA_MNAME': 'polaris.example.com.',
    'SOA_RNAME': 'hostmaster.polaris.example.com.',
    'SOA_SERIAL': 1,
    'SOA_REFRESH': 3600,
    'SOA_RETRY': 600,
    'SOA_EXPIRE': 86400,
    'SOA_MINIMUM': 1,
    'SOA_TTL': 86400,

    'SHARED_MEM_HOSTNAME': '127.0.0.1',
    'SHARED_MEM_STATE_TIMESTAMP_KEY': 'polaris_health:state_timestamp',
    'SHARED_MEM_PPDNS_STATE_KEY': 'polaris_health:ppdns_state',
    'SHARED_MEM_SOCKET_TIMEOUT': 1,

    'LOG': False,

    # copied from POLARIS_INSTALL_PREFIX env when the configuration is loaded
    'INSTALL_PREFIX': None,
}

TOPOLOGY_MAP = {}
