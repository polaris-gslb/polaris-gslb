import os
import sys
import inspect
from shutil import copy

from setuptools import setup, find_packages

INSTALL_PREFIX = '/opt/polaris'

# determine directory where setup.py is located
PWD = os.path.abspath(
    os.path.split(inspect.getfile( inspect.currentframe( ) ))[0])

# load version
sys.path.insert(0, PWD)
from version import version

setup (
    version=version,
    author='Anton Gavrik',    
    name='polaris',
    description='DNS-based traffic manager(GSLB)',
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
        '{}/run'.format(INSTALL_PREFIX)
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

