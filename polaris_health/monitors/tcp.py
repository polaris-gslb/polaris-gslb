# -*- coding: utf-8 -*-

import logging
import re

from polaris_health import Error, ProtocolError, MonitorFailed
from polaris_health.protocols.tcp import TCPSocket
from . import BaseMonitor

__all__ = [ 'TCPConnect', 'TCPContent' ]

LOG = logging.getLogger(__name__)
LOG.addHandler(logging.NullHandler())

# use up to this num of bytes from a response
MAX_RESPONSE_BYTES = 512

MAX_MATCH_LEN = 128
MAX_SEND_LEN = 256

class TCPBase(BaseMonitor):

    """TCP monitor base"""

    def __init__(self, port, interval=10, timeout=1, retires=2):
        """
        args:
            port: int, port number

            Other args are per BaseMonitor() spec

        """
        super(TCPBase, self).__init__(interval=interval, timeout=timeout,
                                      retries=retires)

        # port
        self.port = port
        if not isinstance(port, int) or port < 1 or port > 65535:
            log_msg = ('port "{}" must be an int between 1 and 65535'.
                       format(port))
            LOG.error(log_msg)
            raise Error(log_msg)

class TCPConnect(TCPBase):

    """TCP connect monitor"""

    def run(self, dst_ip):
        """
        Connect to a given destination on TCP.

        args:
            dst_ip: IP address of the destination, string

        raises:
            MonitorFailed() on timeout

        """
        tcp_sock = TCPSocket(ip=dst_ip, port=self.port, 
                             timeout=self.timeout)

        try:
            tcp_sock.connect()
        except ProtocolError as e:
            raise MonitorFailed(e)

        tcp_sock.close()

class TCPContent(TCPBase):

    """TCP content check monitor"""     

    def __init__(self, match, send=None, *args, **kwargs):
        """Connect a tcp socket, optionally send text, read response,
        perform regexp matching.

        args:
            match: string, text to match
            send: string, text to send, before reading response
        """
        super(TCPContent, self).__init__(*args, **kwargs)

        ### match ###
        self.match = match
        if not isinstance(match, str) or len(match) > MAX_MATCH_LEN:
            log_msg = ('match "{}" must be a str, {} chars max'.
                       format(match, MAX_MATCH_LEN))
            LOG.error(log_msg)
            raise Error(log_msg)
        
        # compile regexp obj to use for matching
        try:
            self._match_re = re.compile(self.match, flags=re.I)
        except Exception as e:
            log_msg = ('failed to compile a regular expression from "{}", {}'
                       .format(self.match, e))
            LOG.error(log_msg)
            raise Error(log_msg)

        ### send ###
        self.send = send
        if send is not None:
            if not isinstance(send, str) or len(send) > MAX_SEND_LEN:
                log_msg = ('send "{}" must be a str, {} chars max'.
                       format(send, MAX_SEND_LEN))
                LOG.error(log_msg)
                raise Error(log_msg)

            # convert to bytes for sending over network
            self.send = self.send.encode()

    def run(self, dst_ip):
        """Connect a tcp socket, if self.send is not None, send it to 
        the socket, read response and perform regexp matching.

        args:
            dst_ip: string, IP address to connect to

        """
        tcp_sock = TCPSocket(ip=dst_ip, port=self.port, timeout=self.timeout)

        try:
            tcp_sock.connect()
            # if we have stuff to send, send it, before reading response
            if self.send is not None:
                tcp_sock.sendall(self.send)
            response_bytes = tcp_sock.receive()
        except ProtocolError as e:
            raise MonitorFailed(e)

        # decode up to MAX_RESPONSE_BYTES
        response_text = response_bytes[:MAX_RESPONSE_BYTES].decode()

        # close the socket
        tcp_sock.close()

        # perform regexp matching
        if not self._match_re.search(response_text):
            raise MonitorFailed('failed to match')

