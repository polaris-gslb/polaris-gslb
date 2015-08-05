#-*- coding: utf-8 -*-

import logging

from .core import Distributor

__all__ = [ 'main' ]

LOG = logging.getLogger(__name__)
LOG.addHandler(logging.NullHandler())

def main():
    try:
        Distributor().run()
    except Exception as e:
        LOG.error('crashed - "{}"'.format(e))

