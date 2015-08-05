# -*- coding: utf-8 -*-

import logging

from polaris.health.core.reactor import Reactor

LOG = logging.getLogger(__name__)
LOG.addHandler(logging.NullHandler())

# application entry point
def main():
    reactor = Reactor()

