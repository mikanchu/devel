

import os
import sys
import random

from twisted.internet import reactor
from twisted.internet.defer import Deferred, DeferredList

if __name__ == '__main__':
    import os.path as _p
    sys.path.insert(0, _p.abspath(_p.join(_p.dirname(_p.abspath(sys.argv[0])), '..')))

from logs import lg

from lib import bpio
from lib import udp
from lib import settings

# from stun import stun_client
# from dht import dht_service

#------------------------------------------------------------------------------ 

def listen(local_port, servers, incomings_filename):
    def _loop():
        incomings = []
        for line in open(incomings_filename).read().split('\n'):
            addr = line.split(':')
            addr[1] = int(addr[1])
            incomings.append(addr)
        if len(incomings):
            for srv in servers:
                udp.send_command(local_port, udp.CMD_PING, 'ping', srv)
            for inc in incomings:
                udp.send_command(local_port, udp.CMD_PING, 'ping', inc)
        reactor.callLater(5, _loop)
    _loop()

def connect(local_port, remote_ip, servers, min_port, max_port):
    def _loop():
        for srv in servers:
            udp.send_command(local_port, udp.CMD_PING, 'ping', srv)
        for port_num in range(min_port, max_port+1):
            udp.send_command(local_port, udp.CMD_PING, 'ping', (remote_ip, port_num))
        reactor.callLater(5, _loop)
    _loop()

def datagram_received(datagram, address, local_port):
    try:
        cmd, payload = datagram
    except:
        return
    # if cmd != udp.CMD_PING:
        # return
    print 'datagram [%s] from %r' % (payload, address)
#    if address[0] == sys.argv[1]:
#        print 'OKAY!!!!!!!!!!!!!!', address
#        udp.send_command(local_port, udp.CMD_PING, 'ok', address)
#        # reactor.stop()

def main():
    if len(sys.argv) <= 1:
        print 'usage:'
        print '    natpunch.py server [min port] [max port]'
        print '    natpunch.py listen [local port] [servers list filename] [incoming connections filename]'
        print '    natpunch.py connect [local port] [remote IP] [servers list file] [min port] [max port]'
        return

    lg.set_debug_level(24)
    bpio.init()
    
    if sys.argv[1] == 'server':
        min_port = int(sys.argv[2])
        max_port = int(sys.argv[3])
        for port_num in range(min_port, max_port+1):
            udp.listen(port_num)
            udp.proto(port_num).add_callback(lambda d,a: datagram_received(d, a, port_num))
            
    elif sys.argv[1] == 'listen':
        port_num = int(sys.argv[2])
        udp.listen(port_num)
        udp.proto(port_num).add_callback(lambda d,a: datagram_received(d, a, port_num))
        servers = []
        for line in open(sys.argv[3]).read().split('\n'):
            addr = line.split(':')
            addr[1] = int(addr[1])
            servers.append(addr)
        listen(port_num, servers, sys.argv[4])
        
    elif sys.argv[1] == 'connect':
        port_num = int(sys.argv[2])
        remote_ip = sys.argv[3]
        udp.listen(port_num)
        udp.proto(port_num).add_callback(lambda d,a: datagram_received(d, a, port_num))
        servers = []
        for line in open(sys.argv[4]).read().split('\n'):
            addr = line.split(':')
            addr[1] = int(addr[1])
            servers.append(addr)
        min_port = int(sys.argv[5])
        max_port = int(sys.argv[6])
        connect(port_num, remote_ip, servers, min_port, max_port)
        
    reactor.run()

if __name__ == '__main__':
    main()
    