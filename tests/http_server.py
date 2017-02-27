#!/usr/bin/env python3
 
from http.server import BaseHTTPRequestHandler, HTTPServer
 

class HTTPServerRequestHandler(BaseHTTPRequestHandler):
 
  def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type','text/html')
        self.end_headers()
        body = "This is test"
        self.wfile.write(bytes(body, "utf8"))
        return
 
def run():
  server_address = ('127.0.0.1', 8081)
  httpd = HTTPServer(server_address, HTTPServerRequestHandler)
  httpd.serve_forever()
 
run()

