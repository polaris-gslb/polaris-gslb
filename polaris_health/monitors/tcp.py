# -*- coding: utf-8 -*-

import logging
import re

from polaris_health import Error, ProtocolError, MonitorFailed
from polaris_health.protocols.tcp import TCPSocket
from . import BaseMonitor

__all__ = [ 'TCP' ]

LOG = logging.getLogger(__name__)
LOG.addHandler(logging.NullHandler())

# use up to this num of bytes from a response
MAX_RESPONSE_BYTES = 512

# maximum allowed length of match_re parameter
MAX_MATCH_RE_LEN = 128

# maximum allowed length of send parameter
MAX_SEND_LEN = 256

class TCP(BaseMonitor):

    """TCP monitor base"""

    def __init__(self, port, send=None, match_re=None,
                 interval=10, timeout=1, retires=2):
        """
        args:
            port: int, port number
            send: string, a text to send, before reading response
            match_re: string, a regular expression to search for in a response

            Other args as per BaseMonitor() spec

        """
        super(TCP, self).__init__(interval=interval, timeout=timeout,
                                      retries=retires)

        ### port ###
        self.port = port
        if not isinstance(port, int) or port < 1 or port > 65535:
            log_msg = ('port "{}" must be an integer between 1 and 65535'.
                       format(port))
            LOG.error(log_msg)
            raise Error(log_msg)

        ### match_re ###
        self.match_re = match
        self._match_re_compiled = None
        if self.match_re is not None:
            if not isinstance(match_re, str) \
                    or len(match_re) > MAX_MATCH_RE_LEN:
                log_msg = ('match_re "{}" must be a string, {} chars max'.
                           format(match_re, MAX_MATCH_RE_LEN))
                LOG.error(log_msg)
                raise Error(log_msg)
            
            # compile regexp obj to use for matching
            try:
                self._match_re_compiled = re.compile(self.match_re, flags=re.I)
            except Exception as e:
                log_msg = ('failed to compile a regular '
                           'expression from "{}", {}'
                           .format(self.match_re, e))
                LOG.error(log_msg)
                raise Error(log_msg)

        ### send ###
        self.send = send
        self._send_bytes = None
        if send is not None:
            if not isinstance(send, str) or len(send) > MAX_SEND_LEN:
                log_msg = ('send "{}" must be a string, {} chars max'.
                       format(send, MAX_SEND_LEN))
                LOG.error(log_msg)
                raise Error(log_msg)

            # convert to bytes for sending over network
            self._send_bytes = self.send.encode()

    def run(self, dst_ip):
        """
        Connect a tcp socket 
        If we have a text to send, send it to the socket
        If have a regexp to match, read response and match the regexp

        args:
            dst_ip: string, IP address to connect to

        returns:
            None

        raises:
            MonitorFailed() on a socket operation timeout/error or if failed
            match the regexp.

        """
        tcp_sock = TCPSocket(ip=dst_ip, port=self.port, timeout=self.timeout)

        # connect socket, send text if required
        try:
            tcp_sock.connect()
            if self.send is not None:
                tcp_sock.sendall(self._send_bytes)
        except ProtocolError as e:
            raise MonitorFailed(e)

        # if we have nothing to match, close the socket and return
        if self.match_re is None:
            tcp_sock.close()
            return

        # we have a regexp to match, read response, perform matching
        try:
            response_bytes = tcp_sock.receive()
        except ProtocolError as e:
            raise MonitorFailed(e)
        else:
            # close the socket
            tcp_sock.close()

            # decode up to MAX_RESPONSE_BYTES
            response_text = response_bytes[:MAX_RESPONSE_BYTES].decode()
            
            # match regexp
            if not self._match_re_compiled.search(response_text):
                raise MonitorFailed('failed to match the regexp')

