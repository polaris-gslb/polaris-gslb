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

MIN_EXPECTED_CODES_LEN = 1
MAX_EXPECTED_CODES_LEN = 3
MIN_EXPECTED_CODE = 100
MAX_EXPECTED_CODE = 599


class HTTP(BaseMonitor):

    """HTTP monitor"""    

    def __init__(self, use_ssl=False, hostname=None, url_path='/', port=None,
                 expected_codes=None, interval=10, timeout=5, retries=2):
        """
        args:
            use_ssl: bool, whether to use SSL
            hostname: server's hostname, this will be supplied 
                in "Host:" header, for SSL this will also be supplied via SNI 
            url_path: str, URL url_path
            port: port number to use, by default port 80 will be used (443 if
                use_ssl is True)
            expected_codes: list of ints, HTTP codes to expect in a response,
                if not provided code 200 will be expected by default

            Other args as per BaseMonitor() spec
        """
        super(HTTP, self).__init__(interval=interval, timeout=timeout,
                                         retries=retries)
       
        # name to show in generic state export
        self.name = 'http'

        ### use_ssl ###
        self.use_ssl = use_ssl
        if not isinstance(use_ssl, bool):
            log_msg = 'use_ssl "{}" must be a bool'.format(use_ssl)
            LOG.error(log_msg)
            raise Error(log_msg)

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

        ### expected_codes ###
        self.expected_codes = expected_codes
        # if expected_codes hasn't been set, assign a default
        if expected_codes is None:
                self.expected_codes = [ 200 ]
        # if expected_codes has been set, validate it
        else:
            # must be a list of a certain length
            if not isinstance(expected_codes, list) \
                    or len(expected_codes) < MIN_EXPECTED_CODES_LEN \
                    or len(expected_codes) > MAX_EXPECTED_CODES_LEN:
                log_msg = ('expected_codes "{}" must be a list between '
                           '{} and {} elements'.
                           format(expected_codes, 
                                  MIN_EXPECTED_CODES_LEN,
                                  MAX_EXPECTED_CODES_LEN))
                LOG.error(log_msg)
                raise Error(log_msg)
        
            # each code must be an int within certain boundaries
            for code in expected_codes:
                if not isinstance(code, int) \
                        or code < MIN_EXPECTED_CODE \
                        or code > MAX_EXPECTED_CODE:
                    log_msg = ('expected code "{}" must be an int '
                               'between {} and {}'.
                               format(code, 
                                      MIN_EXPECTED_CODE,
                                      MAX_EXPECTED_CODE))
                    LOG.error(log_msg)
                    raise Error(log_msg)

        # remove duplicate codes
        self.expected_codes = list(set(self.expected_codes))

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

        if response.status_code not in self.expected_codes:
            raise MonitorFailed(
                '{} {}'.format(response.status_code, response.status_reason))

