# -*- coding: utf-8 -*-

import logging

from polaris_health import Error, MonitorFailed
from . import BaseMonitor


__all__ = [ 'Forced' ]

LOG = logging.getLogger(__name__)
LOG.addHandler(logging.NullHandler())


class Forced(BaseMonitor):

    """Forced monitor."""

    def __init__(self, status="up", interval=3600, timeout=1, retries=0):
        """
        args:
            status: string, one of "up", "down", forces the monitor
                to either always succeed of fail. 

            Other args as per BaseMonitor() spec
        """
        super(Forced, self).__init__(interval=interval, timeout=timeout,
                                      retries=retries)

        # name to show in generic state export
        self.name = 'forced'

        ### status ###
        self.status = status
        self._match_re_compiled = None
        if self.status not in [ "up", "down" ]:
                log_msg = ('status "{}" must be either "up" or "down"'.
                           format(status))
                LOG.error(log_msg)
                raise Error(log_msg)

    def run(self, dst_ip):
        """
        args:
            dst_ip: string, IP address to check

        returns:
            None

        raises:
            MonitorFailed() when self.status is "down"
        """
        if self.status == "up":
            return
        else:
            raise MonitorFailed("forced status DOWN")
