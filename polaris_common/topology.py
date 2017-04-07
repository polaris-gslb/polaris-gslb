# -*- coding: utf-8 -*-

import ipaddress


__all__ = [ 
    'config_to_map',
    'get_region'
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
                ip_network('10.1.1.0/24'): 'region1',
                ip_network('10.1.10.0/24'): 'region1',
                ip_network('172.16.1.0/24'): 'region1',

                ip_network('192.168.1.0/24'): 'region2',
                ip_network('10.2.0.0/16'): 'region2',
            }

    raises:
        ValueError: if a region value is "_default"
    """
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
    the given IP address, if multiple networks contain the IP,
    region of the most specific(longest prefix length) match is returned,
    if multiple equal prefix length found the behavior of which 
    entry is returned is undefined.

    args:
        ip_str: string representing an IP address

    returns:
        string: region name
        None: if no region has been found

    raises:
        ValueError: raised by ipaddress if ip_str isn't a valid IP address
    """ 
    ip = ipaddress.ip_address(ip_str)

    # find all the matching networks
    matches = []
    for net in topology_map:
        if ip in net:
            matches.append(net)

    # if only a single match is found return it
    if len(matches) == 1:
        return topology_map[matches[0]]
    # if more than 1 match is found, sort the matches
    # by prefixlen, return the longest prefixlen entry
    elif len(matches) > 1:
        matches.sort(key=lambda net: net.prefixlen)
        return topology_map[matches[-1]]

    # no matches found
    return None

