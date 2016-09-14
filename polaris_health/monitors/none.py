# -*- coding: utf-8 -*-

from . import BaseMonitor

__all__ = [ 'NONE' ]

class NONE(BaseMonitor):

    """NONE monitor base"""

    def __init__(self, port=None, send_string=None, match_re=None,
                 interval=10, timeout=5, retries=2):

        super(NONE, self).__init__(interval=interval, timeout=timeout,
                                      retries=retries)

        self.name = 'none'

    def run(self, dst_ip):

        return

