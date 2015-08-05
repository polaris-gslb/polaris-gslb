# -*- coding: utf-8 -*-

import logging
import ipaddress

import polaris
from polaris import Error

__all__ = [ 'get_region' ]

LOG = logging.getLogger(__name__)
LOG.addHandler(logging.NullHandler())

def get_region(ip_str):
    """Return name of a region from the topology map for
    the given IP address

    args:
        ip_str: string, IP address

    returns:
        string: region name or None if no region has been found
    """    
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError as e:
        LOG.error(e)
        raise Error(e)

    for net in polaris.config.topology:
        if ip in net:
            return polaris.config.topology[net]

    return None

