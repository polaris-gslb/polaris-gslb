## Polaris - guiding the traffic home.

DNS-based Traffic Manager (Global Server Load Balancing).

* A simple, versatile GSLB solution
* Built as an extension to [PowerDNS Authoritative Server](https://www.powerdns.com/auth.html)
* Features:
 * Load-balancing methods:
   * Weighted round-robin
    * Topology(direct clients to the end-points in the same region/datacenter)
 * Parametrized(timeout, interval, retries etc.) health monitors:
    * TCP
     * HTTP
 * Up to 32 addresses returned in a response
 * Different ways to handle all-pool-members-DOWN situation(fallback): REFUSE, answer with NOERROR and an empty data set or any end-points configured configured.

See [WIKI](https://github.com/polaris-gslb/polaris-core/wiki) for more information.

![](https://github.com/polaris-gslb/polaris-core/wiki/overview.jpg)

