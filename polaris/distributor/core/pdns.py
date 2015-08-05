# -*- coding: utf-8 -*-

import sys
import os
import json
import time
import logging

__all__ = [ 'RemoteBackend' ]

LOG = logging.getLogger(__name__)
LOG.addHandler(logging.NullHandler())

class RemoteBackend:

    """PowerDNS Remote Backend handler 

    Implements pipe handler for PowerDNS Remote Backend JSON API:      
    https://doc.powerdns.com/md/authoritative/backend-remote/

    Child classes must implement self.do_<something>(params)
    methods for JSON API calls they need to handle, where <something> 
    must match an exact JSON API method name.
    """

    def __init__(self):
        self.__reader = sys.stdin
        self.__writer = sys.stdout

        # children "do_<something>" methods must set these 
        # result MUST be either True, False or a list
        self.result = False
        # log MUST be a list
        self.log = []

        # this will store the request string
        self.__request = None

    ########################
    ### public interface ###
    ########################
    def run(self):
        """Start the main loop execution"""
        self.__main_loop()

    def add_record(self, qtype, qname, content, ttl):
        """Add a record to the response (self.result)

        args:
            qtype: string, e.g. "ANY"
            qname: string, e.g. "host1.test.com"
            content: string, e.g. "192.168.1.1"
            ttl: string or int, e.g.: 1
        """
        # self.result is False by default, make it a list
        if not isinstance(self.result, list):
            self.result = []

        self.result.append({
            'qtype': qtype,
            'qname': qname,
            'content': content,
            'ttl': ttl
        })

    #############################################
    ### internal do_ methods, do not override ###
    #############################################
    def do_initialize(self, params):
        """Initialization handler

        """
        self.log.append('Polaris Remote Backend initialized')
        self.result = True

    #########################
    ### private interface ###
    #########################
    def __main_loop(self):
        """Main program loop, reads JSON requests from stdin,
        writes JSON responses to stdout
        """
        while(True):
            # reset result and log
            self.result = False
            self.log = []

            # get the request string, strip the ending "\n"
            self.__request  = self.__reader.readline().rstrip()

            # store the start time
            self._start_time = time.time()

            # pdns sends an empty line to signal exit
            if self.__request == '':
                LOG.info('received empty line, exiting')
                return

            # deserialize input
            try:
                obj = json.loads(self.__request)
            except ValueError:
                self.log = [ 'cannot parse input "{}"'.format(self.__request) ]
                self.__write_response()
                return

            # get method name
            method_name = 'do_{}'.format(obj['method'])

            try:
                # get method
                method = getattr(self, method_name)
            except AttributeError:
                self.result = False
                self.log = [ 'method "{}" is not implemented, request was "{}"'
                             .format(method_name, self.__request)]
                self.__write_response()
                continue

            # test
            #method(obj['parameters'])

            # execute method
            try:
                method(obj['parameters'])      
            except Exception:
                self.result = False
                self.log = [ 'method "{}" failed to execute, request was "{}"'.
                            format(method_name, self.__request)]
                self.__write_response()
                continue

            # write response
            self.__write_response()

    def __write_response(self):
        """Construct a response object from
        self.result and self.log and write the response to writer.

        The object must comform to PowerDNS JSON API spec:

        "You must always reply with JSON hash with at least one key, 'result'. 
        This must be boolean false if the query failed. Otherwise it must
        conform to the expected result. 

        You can optionally add 'log' array, each line in this array will be 
        logged in PowerDNS."
        """
        obj = {}
        obj['result'] = self.result

        # store request and response JSON objects
        log_str = 'request: {} '.format(self.__request)
        log_str += 'response: {} '.format(json.dumps(self.result))

        # store PID of the process
        log_str += 'pid: {} '.format(os.getpid())

        # store how long it took to process the request
        time_taken = time.time() - self._start_time
        log_str += 'time_taken: {:6f}s '.format(time_taken)

        # if a method added anything into self.log
        # join it into a string and append to log_str
        if self.log:
            log_str += ' '.join(self.log)

        # do not sent log to the pdns, will output to a file instead    
        # response 'log' field must be an array
        # obj['log'] = [ log_str ] <- this will log to pdns
        self.__writer.write(json.dumps(obj))
        self.__writer.write('\n')
        self.__writer.flush()

        # write log
        LOG.info(log_str)

