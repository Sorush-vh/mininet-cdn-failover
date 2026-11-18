from mininet.topo import Topo
from mininet.net import Mininet
from mininet.link import TCLink
from mininet.cli import CLI
from mininet.node import OVSBridge
import time

class CDNTopo(Topo):
    def build(self):
        switch = self.addSwitch('s1', cls=OVSBridge)

        # Define Infrastructure Hosts
        origin = self.addHost('origin', ip='10.0.0.1')
        edge1 = self.addHost('edge1', ip='10.0.0.2')
        edge2 = self.addHost('edge2', ip='10.0.0.3')
        controller = self.addHost('controller', ip='10.0.0.10')
        client = self.addHost('client', ip='10.0.0.20')

        self.addLink(origin, switch, cls=TCLink, bw=100, delay='200ms')
        self.addLink(edge1, switch, cls=TCLink, bw=50, delay='5ms')
        self.addLink(edge2, switch, cls=TCLink, bw=50, delay='5ms')
        self.addLink(controller, switch, cls=TCLink, bw=10, delay='5ms')
        self.addLink(client, switch, cls=TCLink, bw=20, delay='10ms')

def start_cdn_services(net):
    print("\n*** Booting up CDN Back-end Infrastructure Services...")

    origin = net.get('origin')
    controller = net.get('controller')
    edge1 = net.get('edge1')
    edge2 = net.get('edge2')

    print("--> Starting Master Origin Server (Host: origin)...")
    origin.popen('python3 -u origin_server.py 80')
    time.sleep(1)

    print("--> Starting Central Status Controller (Host: controller)...")
    controller.popen('python3 -u controller.py')
    time.sleep(1)

    print("--> Starting Edge Server Node 1 (Host: edge1)...")
    edge1.popen('python3 -u edge_server.py edge1 10.0.0.2')

    print("--> Starting Edge Server Node 2 (Host: edge2)...")
    edge2.popen('python3 -u edge_server.py edge2 10.0.0.3')

    print("*** All background instances initialized. Waiting for cluster synchronization...\n")
    time.sleep(3)

if __name__ == '__main__':
    topo = CDNTopo()
    net = Mininet(topo=topo, link=TCLink, controller=None)
    net.start()

    start_cdn_services(net)

    print("*** CDN Topology successfully deployed. You can now execute Client test scripts.")
    CLI(net)

    print("\n*** Stopping virtual infrastructure and clean-reaping background threads...")
    net.stop()