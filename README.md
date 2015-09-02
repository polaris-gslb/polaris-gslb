## Polaris - guiding the traffic home.

A simple, extendable Global Server Load Balancing(GSLB) solution, DNS-based traffic manager.

* Built as an enhancement to [PowerDNS Authoritative Server](https://www.powerdns.com/auth.html)
* Features:
 * Load-balancing methods:
   * Weighted round-robin
    * Topology(direct clients to the end-points in the same region/datacenter)
 * Parametrized(timeout, interval, retries etc.) health monitors:
    * TCP
     * HTTP
 * Up to 32 addresses returned in a response
 * Different ways to handle all-pool-members-DOWN situation(fallback): REFUSE, answer with NOERROR and an empty data set or any configured end-points.

See the [WIKI](https://github.com/polaris-gslb/polaris-core/wiki) for installation, configuration and other information.

![](https://github.com/polaris-gslb/polaris-core/wiki/overview.jpg)

