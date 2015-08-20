## 0.3
- Split polaris-core into two individual repositories
 - polaris-health - generic GSLB end-point configuration and health monitoring 
 - polaris-pdns - PowerDNS Remote Backend distributor plugin(to be eventually re-written in a compiled language e.g. Go)
- Make polaris-health to expose the health state table into a shared memory using various formats, controlled by a plugin architecture
 - Implement generic plugin that will push a JSON representation containing every attribute of the health state table, this can be used for monitoring or other applications requiring to track health state of end-points  
 - Implement polaris-pdns plugin that will push a pickled dictionary representation ready to be used by polaris-pdns PowerDNS plugin 
- Collapse the existing health monitors, rename some of the options
 - `http_status` and `https_status` will become `http` monitor
 ```yaml
 delay: 10
 timeout: 2
 retries: 2
 port: 443
 use_ssl: true
 method: GET
 hostname: www.example.com
 url_path: /api/v1.0/check?getall=true
 expect_codes:
         - 200
 ```
 - `tcp_connect` and `tcp_content` will become `tcp` monitor
 ```yaml
 delay: 10
 timeout: 2
 retries: 2
 port: 1234
 send: HELLO\n
 expect_regexp: OK
 ```
- Add new pool `fallback` option `nodata`
 - Return `NOERROR` with no data in DNS response
- Make `polaris-health restart` to watch pid file instead of using a constant delay
- Review and improve logging messages
- Review the default monitor option values
- Review the internal tracker timers under a large number of end-points loaded
