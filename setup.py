#-*- coding: utf-8 -*-

"""Polaris setup"""

import os
import sys
import inspect
import shutil
import setuptools


VERSION = '0.4.0'


def main():
    # use value from POLARIS_INSTALL_PREFIX env if set
    try:
        install_prefix = os.environ['POLARIS_INSTALL_PREFIX']
    except KeyError:
        install_prefix = os.path.join(os.sep, 'opt', 'polaris')

    # determine the directory where setup.py is located
    pwd = os.path.abspath(
        os.path.split(inspect.getfile(inspect.currentframe()))[0])

    # setup packages
    setuptools.setup(
        version=VERSION,
        author='Anton Gavrik',    
        name='polaris-gslb',
        description=('A simple, extendable Global Server Load Balancing(GSLB) '
                     'solution, DNS-based traffic manager.'),
        packages = setuptools.find_packages('.'),
        install_requires=[
            'pyyaml',
            'python3-memcached', 
            'python-daemon-3K'
        ],
        license='BSD 3-Clause',
        url='https://github.com/polaris-gslb/polaris-gslb',
        download_url=('https://github.com/polaris-gslb/polaris-gslb/tarball/v{}'
                      .format(VERSION)),
        classifiers=[
            'Programming Language :: Python :: 3',
        ]
    )

    # create directory topology
    for path in [ 
        os.path.join(install_prefix, 'etc'),
        os.path.join(install_prefix, 'bin'),
        os.path.join(install_prefix, 'run'),        
            ]:
        try:
            os.makedirs(path)
        except FileExistsError:
            continue

    # copy files
    for dirname in [ 'etc', 'bin' ]:
        copy_files(os.path.join(pwd, dirname), 
                   os.path.join(install_prefix, dirname))


def copy_files(src_dir, dst_dir):
    """Copy all files from src_dir to dst_dir""" 
    src_files = os.listdir(src_dir)
    for file_name in src_files:
        full_file_name = os.path.join(src_dir, file_name)
        if (os.path.isfile(full_file_name)):
            shutil.copy(full_file_name, dst_dir)


if __name__ == '__main__':
    main()

