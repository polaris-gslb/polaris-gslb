#!/usr/bin/env python3

import yaml

obj = { 
    'pools': {
            'www-example': {
                    'monitor': 'forced',
                    'lb_method': 'wrr',
                    'max_addrs_returned': 1024,
                    'members': []
                    }
            },
    'globalnames': {
            'www.example.com': {
                    'pool': 'www-example',
                    'ttl': 1,
                    }
            }
}
for b in range(5):
    for i in range(256):
        m = {
            'ip': '127.0.%s.%s' % (b, i),
            'name': 'localhost',
            'weight': 1
            }

        obj['pools']['www-example']['members'].append(m)

print(yaml.dump(obj))
