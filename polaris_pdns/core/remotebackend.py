# -*- coding: utf-8 -*-

import sys
import os
import json
import time

from polaris_pdns import config


__all__ = [ 'RemoteBackend' ]


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
        # log MUST be an array
        self.log = []

        # this will store the request string
        self.__request = None

    ########################
    ### public interface ###
    ########################
    def run(self):
        # run additonal startup tasks if defined by a child class
        self.run_additional_startup_tasks()

        # start the main loop execution
        self.__main_loop()

    def run_additional_startup_tasks(self):
        """Can be overwritten by a child class"""
        return

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
        """The main program loop, reads JSON requests from stdin,
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

            # when pdns is exiting it sends an empty line
            if self.__request == '':
                return

            # deserialize input
            try:
                obj = json.loads(self.__request)
            except ValueError:
                self.log.append('error: cannot parse input "{}"'
                                .format(self.__request))
                self.__write_response()
                return

            # get method name
            method_name = 'do_{}'.format(obj['method'])

            try:
                # get method
                method = getattr(self, method_name)
            except AttributeError:
                self.result = False
                self.log.append('warning: method "{}" is not implemented'
                                .format(method_name, self.__request))
                self.__write_response()
                continue

            # DEBUG ONLY
            #method(obj['parameters'])
            #self.__write_response()
            #continue
            
            # execute method
            try:
                method(obj['parameters'])      
            except Exception:
                self.result = False
                self.log.append('error: method "{}" failed to execute'
                                .format(method_name, self.__request))
                self.__write_response()
                continue
            
            # write response
            self.__write_response()

    def __write_response(self):
        """Construct a response object from
        self.result and self.log and write it to the writer.

        The object must comform to the PowerDNS JSON API spec:

        "You must always reply with JSON hash with at least one key, 'result'. 
        This must be boolean false if the query failed. Otherwise it must
        conform to the expected result. 

        You can optionally add 'log' array, each line in this array will be 
        logged in PowerDNS."
        """
        obj = {}
        obj['result'] = self.result

        # log request and result
        self.log.append('request: {}'.format(self.__request))
        self.log.append('result: {}'.format(self.result))

        # log PID of the process
        self.log.append('pid: {}'.format(os.getpid()))

        # log total time taken to process the request
        time_taken = time.time() - self._start_time
        self.log.append('time taken: {:6f}'.format(time_taken))

        # send log to pdns
        if config.BASE['LOG']:
            # pdns would log entries one at a time
            # which can make it hard to read
            # join log entries into a single string
            # response 'log' field must still be an array
            obj['log'] = [ ' '.join(self.log) ]

        # send the response to pdns
        self.__writer.write(json.dumps(obj))
        self.__writer.write('\n')
        self.__writer.flush()

