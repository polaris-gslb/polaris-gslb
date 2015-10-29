<p align="center"><img src="https://github.com/polaris-gslb/polaris-core/wiki/logo.png"/></p>
<p align="center">Guiding the traffic home</p>

A simple, extendable Global Server Load Balancing(GSLB) solution, DNS-based traffic manager.

* Built as an enhancement for [PowerDNS Authoritative Server](https://www.powerdns.com/auth.html)
* Load-balancing methods:
    * Weighted round-robin
    * Topology(direct clients to the end-points in the same region/datacenter)
* Parameterized(timeout, interval, retries etc.) health monitors:
    * TCP
    * HTTP
* Up to 32 addresses returned in a response
* Different ways to handle the "all-pool-members-down" situation(fallback):
    * return any configured end-points(ignore the health status) 
    * refuse query

See the [WIKI](https://github.com/polaris-gslb/polaris-core/wiki) for installation, configuration and other information.

![](https://github.com/polaris-gslb/polaris-core/wiki/overview.jpg)
