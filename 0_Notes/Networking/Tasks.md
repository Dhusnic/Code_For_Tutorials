# Cisco Packet Tracer Networking Tasks

## Beginner Level:
1. [ ] **Basic PC-to-PC Connection:**
   - Connect two PCs directly with a crossover cable. Assign IP addresses and test connectivity using the `ping` command.

2. [ ] **Single Switch Network:**
   - Connect four PCs to a single switch. Assign IP addresses and test communication between all PCs.

3. [ ] **Simple Router Configuration:**
   - Connect two PCs via a router, configure the router interfaces, and ensure connectivity between the PCs.

4. [ ] **Basic DHCP Setup:**
   - Configure a router to act as a DHCP server for a small LAN. Verify that PCs receive IP addresses automatically.

5. [ ] **Basic Switch Configuration:**
   - Set up a switch with basic settings (hostname, IP address, etc.). Connect a few PCs and test connectivity.

6. [ ] **Static Routing Between Two Routers:**
   - Set up two routers with a connected PC on each side. Configure static routes to allow communication between the PCs.

7. [ ] **Simple Web Server Configuration:**
   - Set up a web server on a PC and another PC as a client. Test access to the web server using the client.

8. [ ] **Basic Telnet Configuration:**
   - Enable Telnet on a router or switch and access it remotely from a PC.

9. [ ] **Single VLAN Configuration:**
   - Create a single VLAN on a switch and assign ports to it. Connect PCs and test connectivity within the VLAN.

10. [ ] **Simple Network with Multiple Switches:**
    - Connect two switches and multiple PCs. Assign IP addresses and verify communication between all devices.

11. [ ] **Basic Network Design with Multiple Routers:**
    - Set up a small network with three routers and configure static routing to enable communication between all subnets.

12. [ ] **Network Address Translation (NAT):**
    - Configure NAT on a router to translate private IP addresses to a public IP address for internet access.

13. [ ] **Simple Network Troubleshooting:**
    - Set up a small network with intentional configuration errors. Identify and fix the errors.

14. [ ] **Basic Wireless Network Configuration:**
    - Configure a wireless router with basic settings and connect a laptop to it. Test wireless connectivity.

15. [ ] **Basic DNS Configuration:**
    - Set up a DNS server on a PC and configure clients to use it. Test domain name resolution.

16. [ ] **Simple File Server Setup:**
    - Set up a file server on a PC and allow another PC to access shared files.

17. [ ] **Basic Network Monitoring with SNMP:**
    - Enable SNMP on a router and monitor it from a PC using SNMP tools.

18. [ ] **Simple Network with a Firewall:**
    - Set up a basic firewall on a router to block certain types of traffic.

19. [ ] **Basic Syslog Configuration:**
    - Configure a router to send log messages to a Syslog server and monitor the logs.

20. [ ] **Basic Network Documentation:**
    - Document a simple network with IP addresses, device names, and configurations.

---

## Intermediate Level:
1. [ ] **Multiple VLANs on a Switch:**
   - Configure multiple VLANs on a switch and assign ports to different VLANs. Test inter-VLAN communication using a router.

2. [ ] **Inter-VLAN Routing with a Router:**
   - Set up a network with two VLANs on a switch and configure a router for inter-VLAN routing.

3. [ ] **OSPF Single Area Configuration:**
   - Configure OSPF on multiple routers within a single area. Verify neighbor relationships and routing tables.

4. [ ] **Configuring RIPv2:**
   - Set up a network with three routers and configure RIPv2 as the dynamic routing protocol. Verify route propagation.

5. [ ] **Advanced NAT Configuration:**
   - Implement PAT (Port Address Translation) to allow multiple devices to share a single public IP address.

6. [ ] **DHCP Relay Agent Configuration:**
   - Configure a DHCP relay agent on a router to forward DHCP requests from one subnet to a DHCP server on another subnet.

7. [ ] **Advanced Access Control Lists (ACLs):**
   - Create ACLs on a router to filter traffic based on various criteria (e.g., source/destination IP, port numbers).

8. [ ] **EtherChannel Configuration:**
   - Set up EtherChannel on a switch to aggregate multiple links into a single logical connection.

9. [ ] **NTP Configuration:**
   - Configure a router to act as an NTP server and synchronize the time on other network devices.

10. [ ] **Basic HSRP Configuration:**
    - Implement HSRP on two routers to provide redundancy for a gateway. Test failover functionality.

11. [ ] **Multicast Routing Configuration:**
    - Set up a network to support multicast traffic using PIM (Protocol Independent Multicast).

12. [ ] **Configuring VTP (VLAN Trunking Protocol):**
    - Set up multiple switches with VTP to manage VLANs centrally. Test VLAN propagation across the network.

13. [ ] **Dynamic Trunking Protocol (DTP) Configuration:**
    - Configure DTP on switches to negotiate trunk links automatically.

14. [ ] **QoS for Voice Traffic:**
    - Implement QoS on a router to prioritize voice traffic over data traffic. Test the impact on call quality.

15. [ ] **Advanced Telnet/SSH Configuration:**
    - Secure Telnet/SSH access to a router or switch using ACLs and encryption.

16. [ ] **Basic IPsec VPN Configuration:**
    - Set up a basic site-to-site VPN using IPsec between two remote offices.

17. [ ] **Configuring Port Security:**
    - Implement port security on a switch to restrict which devices can connect to specific ports.

18. [ ] **Dynamic NAT with Overload:**
    - Configure Dynamic NAT with overload (PAT) to map multiple private IP addresses to a single public IP.

19. [ ] **Basic SNMP Configuration:**
    - Configure SNMP on a router and monitor it using SNMP management software on a PC.

20. [ ] **Basic Network Redundancy with STP:**
    - Implement Spanning Tree Protocol (STP) on a network to prevent loops and provide redundancy.

---

## Advanced Level:
1. [ ] **Advanced OSPF with Multiple Areas:**
   - Configure a multi-area OSPF network with route summarization. Ensure proper routing between areas.

2. [ ] **BGP (Border Gateway Protocol) Configuration:**
   - Set up BGP on routers in different autonomous systems. Implement route filtering and path manipulation.

3. [ ] **Advanced EIGRP Configuration:**
   - Configure EIGRP with route summarization, authentication, and load balancing.

4. [ ] **IPsec VPN with GRE Tunnel:**
   - Set up a GRE tunnel between two sites and secure it with IPsec.

5. [ ] **Advanced ACLs with Time-Based Filters:**
   - Implement time-based ACLs to control access to resources based on the time of day.

6. [ ] **VLAN Security with Private VLANs:**
   - Configure Private VLANs on a switch to isolate certain devices while still providing connectivity.

7. [ ] **Advanced HSRP with Load Balancing:**
   - Configure HSRP with load balancing between two routers. Test the load balancing and failover functionality.

8. [ ] **Implementing MPLS in a Service Provider Network:**
   - Set up MPLS on a network to provide Layer 3 VPN services.

9. [ ] **Network Redundancy with VRRP:**
   - Implement VRRP on routers to provide gateway redundancy. Test failover and redundancy.

10. [ ] **QoS with Class-Based Traffic Shaping:**
    - Implement class-based traffic shaping on a router to manage bandwidth usage for different types of traffic.

11. [ ] **Configuring Dynamic ARP Inspection (DAI):**
    - Set up DAI on a switch to prevent ARP spoofing attacks.

12. [ ] **Network Access Control with 802.1X:**
    - Implement 802.1X on a switch to control access to the network based on authentication.

13. [ ] **Advanced Site-to-Site VPN with DMVPN:**
    - Set up a Dynamic Multipoint VPN (DMVPN) to connect multiple sites with dynamic tunneling.

14. [ ] **Implementing IP Telephony with Call Manager:**
    - Set up an IP telephony network using Cisco Call Manager Express. Configure phones and test calls.

15. [ ] **Advanced IPv6 Network Configuration:**
    - Set up an IPv6 network with multiple subnets, routers, and routing protocols (e.g., OSPFv3, EIGRP for IPv6).

16. [ ] **Network Segmentation with VRF:**
    - Implement Virtual Routing and Forwarding (VRF) to create separate routing tables on a router.

17. [ ] **Implementing Network Automation with Python:**
    - Use Python scripts to automate network configuration and management tasks on Cisco devices.

18. [ ] **Advanced Network Security with Firewalls and IPS:**
    - Configure advanced security features on a router, including firewalls and Intrusion Prevention Systems (IPS).

19. [ ] **Implementing SD-WAN:**
    - Set up an SD-WAN environment to manage wide-area networks with centralized control.

20. [ ] **Network Design and Implementation Project:**
    - Design and implement a complex network from scratch, incorporating all learned concepts (e.g., routing, switching, security, QoS