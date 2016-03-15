# -*- coding: utf-8 -*-

import logging

from polaris_health import Error, ProtocolError, MonitorFailed
from polaris_health.protocols.tcp import TCPSocket
from polaris_health.protocols.http import HTTPRequest
from . import BaseMonitor


__all__ = [ 'HTTP' ]

LOG = logging.getLogger(__name__)
LOG.addHandler(logging.NullHandler())

MAX_URL_PATH_LEN = 256
MAX_HOSTNAME_LEN = 256


class HTTP(BaseMonitor):

    """HTTP monitor"""    

    def __init__(self, use_ssl=False, hostname=None, url_path='/', port=None,
                 interval=10, timeout=2, retries=2):
        """
        args:
            use_ssl: bool, whether to use SSL
            hostname: server's hostname, this will be supplied 
                in "Host:" header, for SSL this will also be supplied via SNI 
            url_path: str, URL url_path
            port: port number to use, by default port 80 will be used (443 if
                use_ssl is True)

            Other args as per BaseMonitor() spec
        """
        super(HTTP, self).__init__(interval=interval, timeout=timeout,
                                         retries=retries)
       
        # name to show in generic state export
        self._name = 'http'

        ### use_ssl ###
        self.use_ssl = use_ssl

        ### url_path ###
        self.url_path = url_path
        if not isinstance(url_path, str) or len(url_path) > MAX_URL_PATH_LEN:
            log_msg = ('url_path "{}" must be a str, {} chars max'.
                       format(url_path, MAX_PATH_LEN))
            LOG.error(log_msg)
            raise Error(log_msg)

        # prepend url_path with "/"
        if not self.url_path.startswith('/'):
            self.url_path = '/{}'.format(self.url_path)

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
        # if port hasn't been set, assign a default
        if port is None:
            if self.use_ssl:
                self.port = 443
            else:
                self.port = 80
        # if port has been set, validate it
        else:
            if not isinstance(port, int) or port < 1 or port > 65535:
                log_msg = ('port "{}" must be an int between 1 and 65535'.
                           format(port))
                LOG.error(log_msg)
                raise Error(log_msg)

    def run(self, dst_ip):
        """Perform GET from a given dst IP address

        args:
            dst_ip: str, IP address of the destination

        raises: MonitorFailed() on error or if status_code != 200

        """
        request = HTTPRequest(ip=dst_ip, 
                              port=self.port,
                              use_ssl=self.use_ssl, 
                              hostname=self.hostname, 
                              url_path=self.url_path,
                              timeout=self.timeout)

        try:
            response = request.get()
        except ProtocolError as e:
            raise MonitorFailed(e)

        if response.status_code != 200:
            raise MonitorFailed(
                '{} {}'.format(response.status_code, response.status_reason))

