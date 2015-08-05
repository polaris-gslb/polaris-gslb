import os
import inspect
from shutil import copy

from setuptools import setup, find_packages

PREFIX = '/opt/polaris'

# determine directory where setup.py is located
PWD = os.path.abspath(
    os.path.split(inspect.getfile( inspect.currentframe( ) ))[0])

setup (
    version='0.2.2',
    author='Anton Gavrik',    
    name='polaris',
    description='DNS-based traffic manager',
    packages=find_packages('.'),
    install_requires=[
        'pyyaml',
        'python3-memcached', 
        'python-daemon-3K'
    ]
)

# create directories
for path in [ 
        '{}/etc/polaris'.format(PREFIX),
        '{}/bin'.format(PREFIX),
        '{}/var/run'.format(PREFIX)
        ]:
    try:
        os.makedirs(path)
    except FileExistsError:
        continue

# copy configuration files
copy('{}/config/base.yaml.dist'.format(PWD), 
     '{}/etc/polaris'.format(PREFIX))

copy('{}/config/lb.yaml.dist'.format(PWD), 
     '{}/etc/polaris'.format(PREFIX))

copy('{}/config/topology.yaml.dist'.format(PWD), 
     '{}/etc/polaris'.format(PREFIX))

# copy executables
copy('{}/bin/polaris-health'.format(PWD),
     '{}/bin'.format(PREFIX))

copy('{}/bin/polaris-distributor'.format(PWD),
     '{}/bin'.format(PREFIX))

copy('{}/bin/check-polaris'.format(PWD),
     '{}/bin'.format(PREFIX))


