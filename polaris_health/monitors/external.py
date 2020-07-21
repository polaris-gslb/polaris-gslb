# -*- coding: utf-8 -*-

import logging
import os
import subprocess

from polaris_health import Error, MonitorFailed
from . import BaseMonitor


__all__ = [ 'External' ]

LOG = logging.getLogger(__name__)
LOG.addHandler(logging.NullHandler())


class External(BaseMonitor):

    """External script monitor base"""

    def __init__(self, port, file_path, result=None, args=None,
                 interval=10, timeout=5, retries=2):
        """
        args:
            port: int, port number
            file_path: string, the full file path to the external check,
                starting at /, must be executable
            args: list, additional command line arguments to be passed to
            the external check
            result: a string to check against the result of the executed script
                any other response will mean a failure.
            Other args as per BaseMonitor() spec
        """
        super(External, self).__init__(interval=interval, timeout=timeout,
                                      retries=retries)

        # name to show in generic state export
        self.name = 'external'

        ### port ###
        self.port = port
        if not isinstance(port, int) or port < 1 or port > 65535:
            log_msg = ('port "{}" must be an integer between 1 and 65535'.
                       format(port))
            LOG.error(log_msg)
            raise Error(log_msg)
        ### file path ###
        if os.path.isfile(file_path):
            ## check if file is executable
            if not os.access(file_path, os.X_OK):
                log_msg = ('file_path "{}" file path is not executable'.
                           format(file_path))
                LOG.error(log_msg)
                raise Error(log_msg)
            self.file_path = file_path
        else:
            log_msg = ('file_path "{}" cannot be found on the system'.
                       format(file_path))
            LOG.error(log_msg)
            raise Error(log_msg)
        ### args ###
        if isinstance(args, list):
            self.args = args
        else:
            self.args = []
        ### result ###
        if type(result) != str:
            log_msg = 'result is not set or is not a string'
            LOG.error(log_msg)
            raise Error(log_msg)
        self.result = result.strip()

    def run(self, dst_ip):
        """
        Execute a shell command script
        Check response matches the result string
        args:
            dst_ip: string, IP address to connect to
        returns:
            None
        raises:
            MonitorFailed() on process timeout or if output does not match result string
            or command returns a non 0 response.
        """
        # force what ever args into strings or subprocess.run will crash
        command = list(map(str, [self.file_path, dst_ip, self.port] + self.args))
        try:
            cmd = subprocess.run(command, universal_newlines=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                        timeout=self.timeout)
        except subprocess.TimeoutExpired as e:
            log_msg = ('command timeout reached: {error}'
                       .format(error=e))
            raise MonitorFailed(log_msg)
        except subprocess.SubprocessError as e:
            raise MonitorFailed(e)

        if cmd.returncode == 0:
            if cmd.stdout.rstrip() == self.result:
                return
            else:
                log_msg = ('The external check returned:{} not {}'.format(cmd.stdout.rstrip(), self.result))
                raise MonitorFailed(log_msg)
        else:
            log_msg = ('External Check Failed: Reason: {}'.format(cmd.stderr.rstrip()))
            raise MonitorFailed(log_msg)
