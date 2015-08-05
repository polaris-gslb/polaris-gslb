## Load balancing configuration lb.yaml

### Monitors

Synopsis:
```yaml
pools:
  test_pool1:
    monitor: https_status
    monitor_params: 
      path: /health.html 
      interval: 30
```

Monitors can have parameters:
```yaml
monitor_params: 
  key1: value1 
  key2: value2
```  

Common optional params:
- interval: how often perform a probe, seconds, min: 1, max: 3600
- timeout: timeout to set on a socket, seconds, min: 0.1, max: 5
- retries: how many times to retry before declaring the member DOWN, min: 0, max: 5

#### http_status, https_status
Perform HTTP(S) GET, succeeds if response HTTP status is 200

monitor_params:
- optional:
 - interval: default 10
 - timeout: default 2
 - retires: default 2
 - path: uri path to request, appended after the member's IP address, default is `/`. For example, setting `path: /health.html` will perform GET against `https://<member_ip>/health.html`.
 - hostname: hostname to supply in HTTP `Host:` header, when using SSL this will also be supplied in SNI, default is None.
 - port: port number, integer between 1 and 65535, by default http_status monitor will use 80, https_status monitor will use 443

Example:
```yaml
pools:
  example1:
    monitor: https_status
    monitor_params:
      hostname: www.example.com
      path: /health.html
      interval: 30
```

#### tcp_connect
Perform a TCP connect, succeeds if socket connected 

monitor_params:
- optional:
 - interval: default 10
 - timeout: default 1
 - retires: default 2
- required:
 - port: port number, integer between 1 and 65535

Example:
```yaml
pools:
  example1:
    monitor: tcp_connect
    monitor_params:
      port: 21
      timeout: 0.1
```

#### tcp_content
Perform a TCP connect, [optionally] send text, read response, succeeds if a pattern matched. 

monitor_params:
- optional:
 - interval: default 10
 - timeout: default 1
 - retries: default 2
 - send: text to send before attempting to read from the socket(use double quotes to make yaml interprete escaped characters e.g. "GET\n")
- required:
 - port: port number, integer between 1 and 65535
 - match: regular expression to search for in the first 512 bytes of response
 
Example:
```yaml
pools:
  example1:
    monitor: tcp_content
    monitor_params:
      port: 9999
      timeout: 0.1
      send: testme
      match: service is up
```

