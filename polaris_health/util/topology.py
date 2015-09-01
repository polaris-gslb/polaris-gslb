# -*- coding: utf-8 -*-

import ipaddress

__all__ = [ 
    'config_to_map',
    'Resolver',
]

def config_to_map(topology_config):
    """
    args:
        topology_config: dict

            {
            'region1': [
                    '10.1.1.0/24',
                    '10.1.10.0/24',
                    '172.16.1.0/24'
                ],
            'region2': [
                    '192.168.1.0/24',
                    '10.2.0.0/16',
                ]
            }

            Region cannot be "_default"

    returns:
        topology_map: dict
            {
                '10.1.1.0/24': 'region1',
                '10.1.10.0/24': 'region1',
                '172.16.1.0/24': 'region1',

                '192.168.1.0/24': 'region2',
                '10.2.0.0/16': 'region2',
            }

    raises:
        ValueError: if a region value is "_default"

    """
    # build topology map from topology_config:
    # {
    #    ipaddress.IPNetwork(): region,
    # }
    topology_map = {}
    for region in topology_config:
        # "_default" cannot be used as a region name
        if region == '_default':
            raise ValueError('cannot use "_default" as a region name')

        for net_str in topology_config[region]:
            net = ipaddress.ip_network(net_str)
            topology_map[net] = region

    return topology_map

def get_region(ip_str, topology_map):
    """Return name of a region from the topology map for
    the given IP address

    args:
        ip_str: string representing an IP address

    returns:
        string: region name
        None: if no region has been found

    raises:
        ValueError: raised by ipaddress if ip_str isn't a valid IP address

    """ 
    ip = ipaddress.ip_address(ip_str)

    for net in topology_map:
        if ip in net:
            return topology_map[net]

    return None

