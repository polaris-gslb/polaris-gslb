# -*- coding: utf-8 -*-

import logging

from polaris import Error, ProtocolError, MonitorFailed
from polaris.health.protocols.tcp import TCPSocket
from polaris.health.protocols.http import HTTPRequest
from . import BaseMonitor

__all__ = [ 'HTTPStatus', 'HTTPSStatus' ]

LOG = logging.getLogger(__name__)
LOG.addHandler(logging.NullHandler())

MAX_PATH_LEN = 256
MAX_HOSTNAME_LEN = 256

class HTTPBase(BaseMonitor):

    """HTTP monitor base"""    

    def __init__(self, use_ssl=False, hostname=None, path='/', port=None,
                 interval=10, timeout=2, retires=2):
        """
        args:
            use_ssl: bool, whether to use SSL
            hostname: server's hostname, this will be supplied 
                in "Host:" header, for SSL this will also be supplied via SNI 
            path: str, URL path
            port: port number to use, by default port 80 will be used (443 if
                use_ssl is True)

            Other args are per BaseMonitor() spec
        """
        super(HTTPBase, self).__init__(interval=interval, timeout=timeout,
                                         retries=retires)
        
        ### use_ssl ###
        self.use_ssl = use_ssl

        ### path ###
        self.path = path
        if not isinstance(path, str) or len(path) > MAX_PATH_LEN:
            log_msg = ('path "{}" must be a str, {} chars max'.
                       format(path, MAX_PATH_LEN))
            LOG.error(log_msg)
            raise Error(log_msg)

        # prepend path with "/"
        if not self.path.startswith('/'):
            self.path = '/{}'.format(self.path)

        ### hostname ###
        self.hostname = hostname
        if hostname is not None:
            if not isinstance(hostname, str) \
                    or len(hostname) > MAX_HOSTNAME_LEN:
                log_msg = ('hostname "{}" must be a str, {} chars max'.
                           format(hostname, MAX_HOSTNAME_LEN))
                LOG.error(log_msg)
                raise Error(log_msg)

        ### port ###
        self.port = port
        # if port has been set, validate it
        if port is not None:
            if not isinstance(port, int) or port < 1 or port > 65535:
                log_msg = ('port "{}" must be an int between 1 and 65535'.
                           format(port))
                LOG.error(log_msg)
                raise Error(log_msg)

        # else(port is None) use default
        else:
            if self.use_ssl:
                self.port = 443
            else:
                self.port = 80

class HTTPStatus(HTTPBase):

    """HTTP status"""

    def run(self, dst_ip):
        """Perform HTTP(S) GET from a given dst IP address

        args:
            dst_ip: str, IP address of the destination

        raises: MonitorFailed() on error or if status_code != 200
        """
        request = HTTPRequest(ip=dst_ip, 
                              port=self.port,
                              use_ssl=self.use_ssl, 
                              hostname=self.hostname, 
                              path=self.path,
                              timeout=self.timeout)

        try:
            response = request.get()
        except ProtocolError as e:
            raise MonitorFailed(e)

        if response.status_code != 200:
            raise MonitorFailed(
                '{} {}'.format(response.status_code, response.status_reason))

class HTTPSStatus(HTTPStatus, HTTPBase):

    """HTTPS status"""

    def __init__(self, *args, **kwargs):
        HTTPBase.__init__(self, *args, use_ssl=True, **kwargs)

