# -*- coding: utf-8 -*-

import logging
import ssl
import re

from polaris_health import ProtocolError
from . import tcp


__all__ = [ 'HTTPRequest' ]

LOG = logging.getLogger(__name__)
LOG.addHandler(logging.NullHandler())

UNVERIFIED_SSL_CONTEXT = ssl._create_unverified_context()


class HTTPResponse:

    """HTTP response"""

    # HTTP Status-Line. group(1) is code, group(2) is reason
    _STATUS_LINE_RE =  re.compile(
        r'^HTTP\/\d\.\d (\d+) ([^\r]*)\r\n', flags=re.I)

    def __init__(self, raw):
        """Parse a raw HTTP response into components and sets:

        self.status_code:
        self.status_reason

        args:
            raw: bytes(), raw HTTP bytes received from a server
        """
        self.raw = raw.decode()

        # set self.status_code, self.status_reason
        self._parse_status()

    def _parse_status(self):
        """Search for HTTP Status-Line in self.raw, parse out status_code and 
        status_reason
        """
        # search for HTTP Status-Line in the beginning of the response
        m = self._STATUS_LINE_RE.search(self.raw[:512])

        # if there is no match, we got a non-http response?
        if not m:
            LOG.debug('Unable to find HTTP Status-Line in the response: {}'
                      .format(self.raw[:512])) 
            raise ProtocolError(
                'Unable to find HTTP Status-Line in the response')

        # convert status to integer
        # as the _STATUS_LINE_RE regexp is matching \d+ 
        # no need to trap ValueError here
        self.status_code = int(m.group(1))
        self.status_reason = m.group(2)


class HTTPRequest:

    """HTTP request"""    

    def __init__(self, ip, use_ssl=False, hostname=None, url_path='/', 
                 port=None, timeout=2):
        """
        args:
            ip: string, ip address to connect to
            use_ssl: bool, whether to use SSL
            hostname: server's hostname, this will be supplied 
                in "Host:" header; when using SSL, this will also be
                supplied via SNI 
            url_path: str, URL url_path, e.g. /index.html
            port: int, port number to use, by default port 80 will be used
                (443 if use_ssl is True)

        """
        ### use_ssl
        self.use_ssl = use_ssl

        ### ip
        self.ip = ip

        # url_path
        self.url_path = url_path
        # prepend url_path with "/"
        if not self.url_path.startswith('/'):
            self.url_path = '/{}'.format(self.url_path)

        ### hostname
        self.hostname = hostname

        ### port
        self.port = port
        # if port is not specified, use 443 with SSL on, 80 with SSL off
        if self.port is None:
            if self.use_ssl:
                self.port = 443
            else:
                self.port = 80

        ### timeout
        self.timeout = timeout

    def get(self):
        """HTTP GET"""

        return self._make(method='GET')

    def _make(self, method='GET'):
        """Make HTTP request

        args:
            method: string, one of GET, POST, PUT

        returns:
            Response() object
        """
        # construct request string
        host_header = ''
        if self.hostname:
            host_header = 'Host: {}\r\n'.format(self.hostname)
        
        # "Host:" header must be provided when using SNI
        req_str = ('{} {} HTTP/1.0\r\n{}Connection: close\r\n\r\n'.
                   format(method, self.url_path, host_header))

        # create a socket
        tcp_sock = tcp.TCPSocket(ip=self.ip, port=self.port,
                                 timeout=self.timeout)

        # if using SSL wrap the socket
        if self.use_ssl:
            tcp_sock.sock = UNVERIFIED_SSL_CONTEXT.wrap_socket(
                tcp_sock.sock, server_hostname=self.hostname)

        # connect
        tcp_sock.connect()
        
        # send bytes
        tcp_sock.sendall(req_str.encode())

        # get response bytes
        raw = tcp_sock.recv()

        # close socket
        tcp_sock.close()

        return HTTPResponse(raw)

