## Polaris - guiding the traffic home.

An extendable Global Server Load Balancing(GSLB) solution, DNS-based traffic manager.

* Built as an enhancement for [PowerDNS Authoritative Server](https://www.powerdns.com/auth.html).
* Load-balancing methods:
    * Weighted round-robin.
    * Topology(direct clients to end-points in the same region/datacenter).
    * Failover group(active-backup).
* Parameterized(timeout, interval, retries etc.) health monitors:
    * TCP
        * Connect to a specific port number.
        * Send string.
        * Match regular expression in response.
    * HTTP/S
        * Port number to use.
        * SSL.
        * Request a specific URL path.
        * Expect a response code from a configurable list.
* Ability to run health checks against an IP that is different from the member IP. 
* Up to 1024 addresses returned in a response.
* Different ways to handle the "all-pool-members-down" situation(fallback):
    * Return any configured end-points(ignore the health status).
    * Refuse query.
* Automatic SOA serial
* A single Health Tracker can serve multiple DNS resolvers running on different machines.
* LB configuration validation on start-up operations.
* Elastic threads pool serving health checks.
* Asynchronous, non-blocking comms between the internal components.

See the [WIKI](https://github.com/polaris-gslb/polaris-core/wiki) for installation, configuration and other information.

![](https://github.com/polaris-gslb/polaris-core/wiki/overview.jpg)
