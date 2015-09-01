#!/bin/env python3
# -*- coding: utf-8 -*-

import json
import time

import memcache

mc = memcache.Client(['127.0.0.1'])

val = mc.get('polaris_health:generic_state')
print(json.dumps(val, indent=4))
#print('\nTimestamp:', time.asctime(time.gmtime(val['timestamp'])))

