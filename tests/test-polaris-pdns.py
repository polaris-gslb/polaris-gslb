#!/usr/bin/env python3

import subprocess
import sys
import time
import json

POLARIS_PDNS_FILE = '/opt/polaris/bin/polaris-pdns'

def pretty_json(s):
        d = json.loads(s)
        return json.dumps(d, indent=4, separators=(',', ': '))


class TestPolarisPDNS:

    def __init__(self, polaris_pdns_file):
        self.proc = subprocess.Popen([ polaris_pdns_file ],
                                     stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE)

    def execute_query(self, query):
        query += '\n'
        self.proc.stdin.write(query.encode())
        self.proc.stdin.flush()

        output = self.proc.stdout.readline().decode()
        return pretty_json(output)

    def prepare_query(self, method, params):
        q = {
            'method': method,
            'parameters': {
                'qtype': params['qtype'],
                'qname': params['qname'],
                'remote': params['remote'],
                'local': params['local'],
                'real-remote': params['real-remote'],
                'zone-id': params['zone-id']
            }
        }

        return json.dumps(q)

    
if __name__ == '__main__':

    t = TestPolarisPDNS(POLARIS_PDNS_FILE)

    method = 'lookup'
    params = {
        'qtype': 'A',
        'qname': 'www.example.com',
        'remote': '10.1.1.21',
        'local': '0.0.0.0',
        'real-remote': '10.1.1.21/32',
        'zone-id': -1
    }
    q = t.prepare_query(method, params)
    print("query: ", pretty_json(q), "\n")
    print("response: ", t.execute_query(q))

    method = 'lookup'
    params = {
        'qtype': 'SOA',
        'qname': 'www.example.com',
        'remote': '10.1.1.21',
        'local': '0.0.0.0',
        'real-remote': '10.1.1.21/32',
        'zone-id': -1
    }
    q = t.prepare_query(method, params)
    print("query: ", pretty_json(q), "\n")
    print("response: ", t.execute_query(q))


