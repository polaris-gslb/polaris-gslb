#!/usr/bin/env python3
 
import socket
    
    
def main():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('127.0.0.1', 5555))
    s.listen(1)
 
    while 1:
        conn, addr = s.accept()
        data = conn.recv(1024)
        conn.close()
        #conn.send(data)


if __name__ == '__main__':
    main()
