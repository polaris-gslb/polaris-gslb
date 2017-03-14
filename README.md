## Polaris - guiding the traffic home.

An extendable Global Server Load Balancing(GSLB) solution, DNS-based traffic manager.

* Built as an enhancement for [PowerDNS Authoritative Server](https://www.powerdns.com/auth.html)
* Load-balancing methods:
    * Weighted round-robin
    * Topology(direct clients to end-points in the same region/datacenter)
    * Failover group(active-backup)
* Parameterized(timeout, interval, retries etc.) health monitors:
    * TCP
        * Port number to use
        * Send string
        * Match regular expression in a response
    * HTTP/S
        * Port number to use
        * SSL
        * Request a specific URL path
        * Expect a response code from a list
* Up to 1024 addresses returned in a response
* Different ways to handle the "all-pool-members-down" situation(fallback):
    * return any configured end-points(ignore the health status) 
    * refuse query
* A single Health Tracker can serve multiple DNS resolver servers running on different machines
* LB configuration validation on restart
* Dynamic threads pool for health checking
* Asynchronous, non-blocking I/O between internal components

See the [WIKI](https://github.com/polaris-gslb/polaris-core/wiki) for installation, configuration and other information.

![](https://github.com/polaris-gslb/polaris-core/wiki/overview.jpg)
