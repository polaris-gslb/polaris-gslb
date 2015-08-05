# -*- coding: utf-8 -*-

import logging
import socket

from polaris import ProtocolError

__all__ = [ 'TCPSocket' ]

LOG = logging.getLogger(__name__)
LOG.addHandler(logging.NullHandler())

# from Python docs: For best match with hardware and network realities,
# the value of bufsize should be a relatively small power of 2, 
# for example, 4096.
RECV_BUFF_SIZE = 1024

class TCPSocket:

    """TCP socket helper"""

    def __init__(self, ip, port, timeout=2):
        self.ip = ip
        self.port = port
        self.timeout = timeout

        # create socket
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        
        # set timeout on the socket
        self.sock.settimeout(self.timeout)

    def connect(self):
        """Connect self.sock to self.ip:self.port"""    
        try:
            self.sock.connect((self.ip, self.port))
        except OSError as e:
            self.sock.close()
            raise ProtocolError(e)

    def sendall(self, b):
        """sendall bytes to connected self.sock

        https://docs.python.org/3.4/library/socket.html#socket.socket.sendall

        args: b, bytes, bytes to send
        """       
        try:
            self.sock.sendall(b)
        except OSError as e:
            self.sock.close()
            raise ProtocolError(e)

    def receive(self): 
        """Receive response ONCE from connected self.sock up to RECV_BUFF_SIZE
                
        returns:
            bytes() received
        """
        try:
            received = self.sock.recv(RECV_BUFF_SIZE)
        except OSError as e:
            self.sock.close()
            raise ProtocolError(e)

        return received

    def close(self):
        """Shut down and close connected self.sock

        """
        # shutdown and close the socket
        self.sock.shutdown(2) # SHUT_RDWR http://linux.die.net/man/2/shutdown
        self.sock.close()

