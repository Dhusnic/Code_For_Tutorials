**OSI Modal - Open System Interconnection**

* This is composed of 7 layer 
*  framework used to understand and implement networking protocols in seven distinct layers

### 7 Layer of OSI Modals
1. Physical Layer
2. Data Link Layer
3. Network Layer 
4. Transport Layer 
5. Session Layer 
6. Presentation Layer
7. Application Layer


Here’s table that includes common networking devices and protocols associated with each OSI model layer:

| Layer Number | Layer Name         | Function                                                              | Key Elements                                                                        | Example Protocols                          | Networking Devices                                                                     |
| ------------ | ------------------ | --------------------------------------------------------------------- | ----------------------------------------------------------------------------------- | ------------------------------------------ | -------------------------------------------------------------------------------------- |
| 1            | Physical Layer     | Deals with the physical connection between devices.                   | Transmission mediums (cables, fiber optics), electrical signals, bit rate, topology | Ethernet (physical aspect), USB, Bluetooth | Hubs, Repeaters, Network Interface Cards (NICs), Cables (Coaxial, Fiber, Twisted Pair) |
| 2            | Data Link Layer    | Provides node-to-node data transfer and handles error correction.     | MAC addresses, frame formatting, error detection/correction, flow control           | Ethernet (data link aspect), PPP, HDLC     | Switches, Bridges, Network Interface Cards (NICs), Wireless Access Points (APs)        |
| 3            | Network Layer      | Manages packet forwarding and routing through different routers.      | Logical addressing (IP addresses), routing, path determination, packet forwarding   | IP, ICMP, OSPF                             | Routers, Layer 3 Switches, Multilayer Switches                                         |
| 4            | Transport Layer    | Ensures end-to-end communication, error recovery, and flow control.   | Segmentation, reassembly, error detection/correction, flow control, multiplexing    | TCP, UDP, SCTP                             | Firewalls (for some transport-level filtering), Gateways                               |
| 5            | Session Layer      | Manages sessions between applications, including connections.         | Session establishment, maintenance, termination, synchronization, dialog control    | NetBIOS, RPC, PPTP                         | Session Border Controllers (SBCs), Application Gateways                                |
| 6            | Presentation Layer | Translates data between the application layer and the network format. | Data translation, encryption/decryption, compression, data format handling          | SSL/TLS, JPEG, ASCII, EBCDIC               | Gateways, Firewalls (for encryption/decryption functions)                              |
| 7            | Application Layer  | Provides network services directly to user applications.              | High-level APIs, user interface, application services                               | HTTP, FTP, SMTP, DNS                       | Firewalls (deep packet inspection), Proxies, Load Balancers                            |

This table includes common networking devices along with the protocols that correspond to each OSI layer. Each device and protocol serves a specific role within its respective layer, contributing to the overall functionality of the network.


![[networking layer.png]]


![[OSI work flow.png]]
Please Don't Touch Superman's Private Area
Here’s a brief description of the OSI model layers in order from the Application Layer to the Physical Layer:

### 1. **Application Layer (Layer 7):** 
Provides network services directly to end-user applications and facilitates user interaction with the network. Examples include email, file transfers, and web browsing.

### 2. **Presentation Layer (Layer 6):** 
Translates and processes data to ensure it's in a usable format for the application layer. It handles data encoding, encryption, and compression.

### 3. **Session Layer (Layer 5):** 
Manages and controls the connections (sessions) between computers. It establishes, maintains, and terminates communication sessions.

### 4. **Transport Layer (Layer 4):** 
Ensures reliable data transfer between end systems. It provides error checking, flow control, and data segmentation. Protocols like TCP and UDP operate at this layer.

### 5. **Network Layer (Layer 3):** 
Handles the routing of data across the network. It uses logical addressing (IP addresses) to determine the best path for data packets to reach their destination.

### 6. **Data Link Layer (Layer 2):** 
Ensures reliable data transfer across the physical network. It formats data into frames and handles error detection, correction, and MAC addressing.

### 7. **Physical Layer (Layer 1):**
Deals with the physical connection between devices. It transmits raw bits over a physical medium and defines the electrical, mechanical, and procedural standards for the connection.



