The solution is implemented in the form of PowerDNS authoritative server
enhancement and consists of:

1) Health tracker - takes in a configuration dictionary specifying pools
of backend servers, associated health checks etc., builds a health state
table, iterates over it periodically and issues health probes that get
processed asynchronously by a pool of worker processes, communication
between the central synchronization process and the workers is
via multiprocessing.Queue(). State information is propagated into a shared
memory(memcache). Runs as a daemon.

2) Distributor - PowerDNS Remote Backend JSON-API client, performs DNS
query distribution according to the health state(sync-ed periodically from
memcache) and the load balancing algorithm selected.

![](overview.jpg)

Some of the supported features:

- Parametrized health checks(retries, interval, timeout etc.):
    - TCP connect(socket open)
    - TCP content(regexp pattern matching)
    - HTTP/S status(match status code).

- Load balancing methods:
    - Weighted round-robin
    - Topology weighted round-robin(distributes queries according to a topology
    map(direct clients to the end-points in the same region/datacenter)).

- Up to 32 addresses returned in a response.

- Different ways to react when all pool members are DOWN(fallback), respond
with: REFUSED, NODATA or any IPs configured.

Example LB configuration:

```yaml
globalnames:
    wiki.myco.com:
        pool: wiki
        ttl: 1

pools:
    myapp:
        fallback: any
        lb_method: twrr
        max_addrs_returned: 2
        members:
            172.16.1.1:
                name: wiki1-dc1
                weight: 3
            10.1.1.2:
                name: wiki2-dc2
                weight: 2
            10.1.1.1:
                name: wiki3-dc2
                weight: 3
        monitor: http_status
        monitor_params:
            hostname: wiki.myco.com
            path: /healthcheck?check_all=1
            port: 81
            frequency: 5
            timeout: 1
```

Example topology configuration:

```yaml
datacenter1:
    - 172.16.1.0/24
datacenter2:
    - 10.1.1.0/16
```

Updating the configuration(involves the health tracker restart) does not impact
front-end DNS resolution and is seamless to the clients.
