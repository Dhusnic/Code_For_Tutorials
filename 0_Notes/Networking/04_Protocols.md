The Comman Types of Protocols
1. [[00_Inventory_Protocols]] 
2. [[00_Discovery_protocols]]
3. [[00_Data_Transfer_Protocols]]

| **Category**                         | **Protocols/Concepts**                                                                                                                                     |
|--------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **Application Layer Protocols**      | HTTP, HTTPS, FTP, SMTP, DNS, POP3, IMAP, Telnet, SNMP, DHCP, NTP, LDAP, SIP, RTSP, NNTP, WMI, SSH                                                            |
| **Transport Layer Protocols**        | TCP, UDP, SCTP, DCCP                                                                                                                                       |
| **Internet/Network Layer Protocols** | IP (IPv4, IPv6), ICMP, IGMP, ARP, RARP, OSPF, BGP, EIGRP, IPsec, Ping, Traceroute, IP Route, IP Forwarding, IP Tunnel, Subnet                               |
| **Data Link Layer Protocols**        | Ethernet, PPP, Frame Relay, MPLS, ATM, HDLC, SLIP, STP, ARP (functions at both the Network and Data Link layers), LLDP, CDP                                |
| **Network Access/Physical Layer**    | Wi-Fi (IEEE 802.11), Ethernet (IEEE 802.3), DSL, ISDN, Bluetooth, Token Ring, GSM, CDMA, LTE, FDDI, Zigbee                                                 |
| **Routing Protocols**                | OSPF, BGP, EIGRP, RIP, IS-IS, IGRP                                                                                                                         |
| **Security Protocols**               | SSL/TLS, IPSec, SSH, HTTPS, Kerberos, PGP, S/MIME, PAP, CHAP, 802.1X                                                                                       |
| **Session Layer Protocols**          | PPTP, L2TP, NetBIOS, RPC, RTCP, H.245                                                                                                                      |
| **Presentation Layer Protocols**     | SSL/TLS (also used in Security), MIME, XDR, ASN.1, X.25                                                                                                    |

This table now includes LLDP, CDP, OSPF, IP Route, IP Forwarding, IP Tunnel, and Subnet within their respective categories.

Certainly! Here’s the list of protocols ordered by their OSI layer in ascending order, including their details:

### 1. **ICMP (Internet Control Message Protocol)**
- **Port Number:** N/A (part of IP protocol)
- **OSI Layer:** Network Layer (Layer 3)
- **Explanation:** ICMP is used for error messages and operational information (e.g., ping).
- **Steps Involved:** 
  1. An error or operational message is generated.
  2. The message is sent to the relevant network device.
- **Advantages:** Useful for network diagnostics and error reporting.
- **Disadvantages:** Limited functionality (no data transport).
- **Speed:** Typically fast, used for quick error reporting.

### 2. **TCP (Transmission Control Protocol)**
- **Port Number:** N/A (part of IP protocol)
- **OSI Layer:** Transport Layer (Layer 4)
- **Explanation:** TCP is a connection-oriented protocol that ensures reliable data transmission.
- **Steps Involved:** 
  1. Connection establishment (Three-way handshake).
  2. Data transmission.
  3. Connection termination.
- **Advantages:** Reliable delivery with error-checking and flow control. Ensures data is received in order.
- **Disadvantages:** More overhead compared to UDP.
- **Speed:** Generally slower than UDP due to error-checking and connection management.

### 3. **UDP (User Datagram Protocol)**
- **Port Number:** N/A (part of IP protocol)
- **OSI Layer:** Transport Layer (Layer 4)
- **Explanation:** UDP is a connectionless protocol that provides faster but less reliable data transmission.
- **Steps Involved:** 
  1. Data is sent without establishing a connection.
  2. No acknowledgment or error-checking.
- **Advantages:** Faster than TCP due to lower overhead. Suitable for applications where speed is critical.
- **Disadvantages:** No guarantee of data delivery or order.
- **Speed:** Generally faster than TCP due to lack of connection management and error-checking.

### 4. **DNS (Domain Name System)**
- **Port Number:** 53
- **OSI Layer:** Application Layer (Layer 7)
- **Explanation:** DNS translates domain names into IP addresses.
- **Steps Involved:** 
  1. Client sends a DNS query to a DNS server.
  2. DNS server looks up the domain and returns the IP address.
- **Advantages:** Enables user-friendly domain names. Supports a hierarchical structure.
- **Disadvantages:** Can be a target for attacks (e.g., DNS spoofing).
- **Speed:** Generally fast, but can vary depending on cache and server load.

### 5. **DHCP (Dynamic Host Configuration Protocol)**
- **Port Number:** 67 (server), 68 (client)
- **OSI Layer:** Application Layer (Layer 7)
- **Explanation:** DHCP dynamically assigns IP addresses and other network configurations to devices.
- **Steps Involved:** 
  1. Client sends a DHCP Discover message.
  2. Server responds with a DHCP Offer.
  3. Client requests the offered IP address (DHCP Request).
  4. Server confirms the assignment (DHCP Acknowledgment).
- **Advantages:** Simplifies network configuration. Reduces manual IP management.
- **Disadvantages:** IP addresses are dynamically assigned and can change.
- **Speed:** Generally quick, but depends on network size and server responsiveness.

### 6. **FTP (File Transfer Protocol)**
- **Port Number:** 21 (control), 20 (data)
- **OSI Layer:** Application Layer (Layer 7)
- **Explanation:** FTP is used for transferring files between a client and a server.
- **Steps Involved:** 
  1. Client connects to the server on port 21 for control.
  2. Authentication (username and password) is performed.
  3. File transfer occurs over port 20.
- **Advantages:** Allows for the transfer of large files. Supports resume of interrupted transfers.
- **Disadvantages:** Transmits data in plain text (not secure).
- **Speed:** Variable, depends on network conditions and server capabilities.

### 7. **SFTP (SSH File Transfer Protocol)**
- **Port Number:** 22
- **OSI Layer:** Application Layer (Layer 7)
- **Explanation:** SFTP is used for secure file transfer over SSH.
- **Steps Involved:** 
  1. Client connects to the server using SSH on port 22.
  2. Authentication occurs.
  3. Files are transferred securely over the same SSH connection.
- **Advantages:** Secure transfer with encryption. Authenticated access.
- **Disadvantages:** More complex setup than FTP.
- **Speed:** Generally similar to FTP but can be affected by encryption overhead.

### 8. **HTTP (Hypertext Transfer Protocol)**
- **Port Number:** 80
- **OSI Layer:** Application Layer (Layer 7)
- **Explanation:** HTTP is used for transferring web pages on the internet.
- **Steps Involved:** 
  1. Client sends an HTTP request to the server.
  2. Server processes the request and sends back an HTTP response.
  3. Client renders the response (usually a web page).
- **Advantages:** Simple and easy to implement. Widely supported across the web.
- **Disadvantages:** Not secure (unencrypted).
- **Speed:** Generally fast, but depends on server and network conditions.

### 9. **HTTPS (Hypertext Transfer Protocol Secure)**
- **Port Number:** 443
- **OSI Layer:** Application Layer (Layer 7)
- **Explanation:** HTTPS is HTTP with encryption (SSL/TLS) for secure communication over a network.
- **Steps Involved:** 
  1. Client initiates a connection to the server using HTTPS.
  2. SSL/TLS handshake occurs to establish a secure connection.
  3. Client sends an encrypted HTTP request.
  4. Server processes and responds with an encrypted HTTP response.
- **Advantages:** Secure communication via encryption. Ensures data integrity and confidentiality.
- **Disadvantages:** Slightly more overhead due to encryption/decryption processes.
- **Speed:** Slightly slower than HTTP due to encryption, but generally fast.

### 10. **POP3 (Post Office Protocol version 3)**
- **Port Number:** 110
- **OSI Layer:** Application Layer (Layer 7)
- **Explanation:** POP3 is used for retrieving emails from a server to a client.
- **Steps Involved:** 
  1. Client connects to the POP3 server.
  2. Authentication occurs.
  3. Emails are downloaded to the client.
- **Advantages:** Simple to implement. Emails stored locally after download.
- **Disadvantages:** Emails are usually removed from the server.
- **Speed:** Generally fast for retrieving emails.

### 11. **IMAP (Internet Message Access Protocol)**
- **Port Number:** 143 (unencrypted), 993 (encrypted)
- **OSI Layer:** Application Layer (Layer 7)
- **Explanation:** IMAP is used for accessing and managing emails on a server.
- **Steps Involved:** 
  1. Client connects to the IMAP server.
  2. Authentication occurs.
  3. Emails are managed and accessed directly on the server.
- **Advantages:** Emails remain on the server (access from multiple devices). Supports folder management.
- **Disadvantages:** Requires constant server connection.
- **Speed:** Generally efficient, but can be slower if the server is overloaded.

### 12. **SMTP (Simple Mail Transfer Protocol)**
- **Port Number:** 25 (default), 587 (for secure submission)
- **OSI Layer:** Application Layer (Layer 7)
- **Explanation:** SMTP is used for sending emails from a client to a server or between servers.
- **Steps Involved:** 
  1. Client connects to the SMTP server.
  2. Client sends email data and recipient information.
  3. Server processes and routes the email.
- **Advantages:** Widely used for email transmission. Supports various email clients.
- **Disadvantages:** Not secure by default (unencrypted).
- **Speed:** Generally fast for small to medium-sized emails.

This ordering reflects the OSI model layers from the Network Layer to the Application Layer.




Here’s the updated table including the additional protocols and concepts:

| **Category**                         | **Protocols/Concepts**                  |
|--------------------------------------|-----------------------------------------|
| **Data Link Layer Protocols**        | LLDP (Link Layer Discovery Protocol), CDP (Cisco Discovery Protocol) |
| **Routing Protocols (Network Layer)**| OSPF (Open Shortest Path First)         |
| **Internet/Network Layer Protocols** | Traceroute, Ping, IP Route, IP Forwarding, IP Tunnel, Subnet |
| **Application Layer Protocols**      | SNMP (Simple Network Management Protocol), WMI (Windows Management Instrumentation), SSH (Secure Shell) |

This table now includes LLDP, CDP, OSPF, IP Route, IP Forwarding, IP Tunnel, Subnet, SNMP, WMI, SSH, Traceroute, and Ping within their respective categories.






Here’s the categorization for each of the specified protocols and concepts:

1. **LLDP (Link Layer Discovery Protocol)**
   - **Category:** **Data Link Layer Protocol**
   - **Purpose:** Used by network devices to advertise their identity and capabilities to directly connected devices on the same network.

2. **CDP (Cisco Discovery Protocol)**
   - **Category:** **Data Link Layer Protocol**
   - **Purpose:** A Cisco proprietary protocol used for discovering and sharing information about directly connected Cisco devices.

3. **OSPF (Open Shortest Path First)**
   - **Category:** **Routing Protocol (Network Layer)**
   - **Purpose:** A link-state routing protocol used to find the best path for data through a network.

4. **IP Route**
   - **Category:** **Routing/Internet Layer Concept**
   - **Purpose:** Refers to the path that IP packets take from the source to the destination. It's a part of the network layer routing process.

5. **IP Forwarding**
   - **Category:** **Internet Layer Concept**
   - **Purpose:** The process used by routers to pass packets from one network interface to another, based on the destination IP address.

6. **IP Tunnel**
   - **Category:** **Internet/Network Layer Concept**
   - **Purpose:** A method used to encapsulate packets inside another packet, enabling them to traverse incompatible networks or provide VPN functionality.

7. **Subnet**
   - **Category:** **Network Layer Concept**
   - **Purpose:** A logical subdivision of an IP network. Subnetting divides a large network into smaller, more manageable sections.
