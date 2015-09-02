#-*- coding: utf-8 -*-

"""Polaris setup script"""

import os
import sys
import inspect
from shutil import copy

from setuptools import setup, find_packages

INSTALL_PREFIX = '/opt/polaris'

# determine the directory where setup.py is located
PWD = os.path.abspath(
    os.path.split(inspect.getfile(inspect.currentframe()))[0])

setup (
    version='0.3.0',
    author='Anton Gavrik',    
    name='polaris-gslb',
    description=('A simple, extendable Global Server Load Balancing(GSLB) '
                 'solution, DNS-based traffic manager.'),
    packages = find_packages('.'),
    install_requires=[
        'pyyaml',
        'python3-memcached', 
        'python-daemon-3K'
    ]
)

# create directories
for path in [ 
        '{}/etc'.format(INSTALL_PREFIX),
        '{}/bin'.format(INSTALL_PREFIX),
        ]:
    try:
        os.makedirs(path)
    except FileExistsError:
        continue

# copy configuration files
copy('{}/config/polaris-health.yaml.dist'.format(PWD), 
     '{}/etc'.format(INSTALL_PREFIX))

copy('{}/config/polaris-lb.yaml.dist'.format(PWD), 
     '{}/etc'.format(INSTALL_PREFIX))

copy('{}/config/polaris-topology.yaml.dist'.format(PWD), 
     '{}/etc'.format(INSTALL_PREFIX))

copy('{}/config/polaris-pdns.yaml.dist'.format(PWD), 
     '{}/etc'.format(INSTALL_PREFIX))

# copy executables
copy('{}/bin/polaris-health'.format(PWD),
     '{}/bin'.format(INSTALL_PREFIX))

copy('{}/bin/polaris-pdns'.format(PWD),
     '{}/bin'.format(INSTALL_PREFIX))

copy('{}/bin/check-polaris-health'.format(PWD),
     '{}/bin'.format(INSTALL_PREFIX))

copy('{}/bin/check-pdns'.format(PWD),
          '{}/bin'.format(INSTALL_PREFIX))

