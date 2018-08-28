# -*- coding: utf-8 -*-

import logging
import socket
import time

from polaris_health import ProtocolError


__all__ = [ 'TCPSocket' ]

LOG = logging.getLogger(__name__)
LOG.addHandler(logging.NullHandler())

# from Python docs: For best match with hardware and network realities,
# the value of bufsize should be a relatively small power of 2, 
# for example, 4096.
RECV_BUFF_SIZE = 8192


class TCPSocket:

    """TCP socket helper"""

    def __init__(self, ip, port, timeout=5, auto_timeout=True):
        """
        auto_timeout: bool, if True the timeout on the socket will
            automatically decrease after every I/O operation by the amount 
            of time it took to complete it.
        """    
        self.ip = ip
        self.port = port
        self.timeout = timeout
        self.auto_timeout = auto_timeout

        # create socket
        if ':' in ip:
            self._sock = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
        else:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        self.settimeout(self.timeout)

    def connect(self):
        """Connect self._sock to self.ip:self.port"""    
        start_time = time.monotonic()
        try:
            self._sock.connect((self.ip, self.port))
        except OSError as e:
            self._sock.close()
            raise ProtocolError('{} {} during socket.connect()'
                                .format(e.__class__.__name__, e))
        self._decrease_timeout(time.monotonic() - start_time)

    def sendall(self, b):
        """sendall bytes to connected self._sock

        https://docs.python.org/3.4/library/socket.html#socket.socket.sendall

        args: b, bytes, bytes to send
        """       
        start_time = time.monotonic()
        try:
            self._sock.sendall(b)
        except OSError as e:
            self._sock.close()
            raise ProtocolError('{} {} during socket.sendall()'
                                .format(e.__class__.__name__, e))
        self._decrease_timeout(time.monotonic() - start_time)

    def recv(self): 
        """Read response ONCE from connected self._sock 
        up to RECV_BUFF_SIZE bytes
                
        returns:
            bytes() received
        """
        start_time = time.monotonic()
        try:
            received = self._sock.recv(RECV_BUFF_SIZE)
        except OSError as e:
            self._sock.close()
            raise ProtocolError('{} {} during socket.recv()'
                                .format(e.__class__.__name__, e))
        self._decrease_timeout(time.monotonic() - start_time)

        return received

    def close(self):
        """Shut down and close connected self._sock"""
        # protect against crashing when called on a non-connected socket
        try:
            # SHUT_RDWR http://linux.die.net/man/2/shutdown
            self._sock.shutdown(2)
            self._sock.close()
        except OSError as e:
            log_msg = ('got {} {} when shutting down and closing the socket'
                      .format(e.__class__.__name__, e))
            LOG.warning(log_msg)
            
    def settimeout(self, timeout):
        """Set timeout on the socket"""
        self._sock.settimeout(timeout)

    def _decrease_timeout(self, time_taken):   
        """When self.auto_timeout is True decrease the value of self.timeout
        by the time_taken and set it on the socket
        """ 
        if self.auto_timeout:
            self.timeout -= time_taken
            if self.timeout < 0:
                self.timeout = 0
            self.settimeout(self.timeout)

