## Installation notes

### Requirements

- PowerDNS
- Python3.4
- memcache
- pyyaml
- python3-memcached
- python-daemon-3K

### PowerDNS

PDNS needs to be compiled with Remote Backend support, example installation from sorce:

```shell
REPO_ROOT=/home/user/polaris-core
PDNS_VERSION=3.4.5

wget -P /tmp/ https://downloads.powerdns.com/releases/pdns-${PDNS_VERSION}.tar.bz2
tar -xvf /tmp/pdns-${PDNS_VERSION}.tar.bz2 -C /tmp
cd /tmp/pdns-${PDNS_VERSION}
./configure --with-modules="remote" && make -j 8 && make install
cp pdns/pdns /etc/init.d/ 
rm -rf /tmp/pdns-${PDNS_VERSION}.tar.bz2 /tmp/pdns-${PDNS_VERSION}

# copy pdns config file, this has all caching disabled
cp ${REPO_ROOT}/config/pdns.conf /usr/local/etc/

# add to startup
chkconfig --add pdns
```

### Polaris core

```
python3 setup.py install
```

This will create the following directory topology:

```
/opt/polaris/
├── bin
│   ├── check-polaris
│   ├── polaris-distributor
│   └── polaris-health
├── etc
│   └── polaris
│       ├── base.yaml.dist
│       ├── lb.yaml.dist
│       └── topology.yaml.dist
└── var
    └── run
```

Copy base.yaml.dist to base.yaml, lb.yaml.dist to lb.yaml and topology.yaml.dist to topology.yaml and review the files.

Set path to python3 executable in `/opt/polaris/bin/polaris-distributor`

Start pdns `/etc/init.d/pdns start`

Use `/opt/polaris/polaris-health [start|restart|stop]` to control the health tracker application.



