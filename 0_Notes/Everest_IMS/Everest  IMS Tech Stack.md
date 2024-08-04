Frontend - HTML , CSS , Angular
Backend - python
wrapper - Django
Testing - Cucumber

## Data Collection
1. SNMP - simple Network Management Protocol (CPU , disk ,memory utilizations)
2. WMI (windows management instrumentation) - WMI query and get utilizations
3. SSH - Security Shell 
4. HTTP - Hypertext Transfer Protocol
### Definition of protocols
#### SNMP (Simple Network Management Protocol)

**Overview**: SNMP is a protocol used for network management. It enables network devices (like routers, switches, servers, printers, etc.) to communicate management information with a network management system.

**Key Features**:
- **Components**: Managed devices, agents, and network management systems (NMS).
- **Operations**: GET, SET, TRAP.
- **Versions**: SNMPv1, SNMPv2c, SNMPv3 (with v3 offering improved security features).

**Example**: A network admin can use SNMP to query a router for its current CPU usage or to change its configuration.

#### WMI (Windows Management Instrumentation)

**Overview**: WMI is a set of specifications from Microsoft for consolidating the management of devices and applications in a network from Windows-based systems.

**Key Features**:
- **Access**: Provides a standardized way for scripts and applications to access management data.
- **Components**: CIM (Common Information Model), WMI providers.
- **Security**: Utilizes Windows authentication.

**Example**: An IT administrator can use WMI to check the status of services on a remote Windows server or to retrieve event log information.

#### SSH (Secure Shell)

**Overview**: SSH is a protocol for securely accessing and managing network devices and servers over an unsecured network.

**Key Features**:
- **Encryption**: Provides strong encryption to ensure data confidentiality.
- **Components**: SSH client, SSH server.
- **Authentication**: Supports multiple methods, including passwords and public key authentication.

**Example**: An admin can use an SSH client to log into a Linux server to execute commands remotely and securely.

#### HTTP (Hypertext Transfer Protocol)

**Overview**: HTTP is the foundational protocol used by the World Wide Web to transfer web pages from servers to browsers.

**Key Features**:
- **Stateless**: Each request from a client to a server is treated as an independent transaction.
- **Methods**: GET, POST, PUT, DELETE, etc.
- **Components**: Web client (browser), web server.

**Example**: A user enters a URL in their browser, which sends an HTTP GET request to a web server. The server responds with the requested web page.

#### Ping

**Overview**: Ping is a utility used to test the reachability of a host on an IP network and to measure the round-trip time for messages sent from the originating host to a destination computer.

**Key Features**:
- **ICMP**: Uses Internet Control Message Protocol (ICMP) echo request and echo reply messages.
- **Function**: Checks connectivity and measures latency.
- **Components**: Ping command, destination host.

**Example**: An admin uses the ping command to check if a server is reachable and to measure the network latency.

#### Differences in a Table

| Feature         | SNMP                                 | WMI                                  | SSH                                  | HTTP                                 | Ping                                 |
|-----------------|--------------------------------------|--------------------------------------|--------------------------------------|--------------------------------------|--------------------------------------|
| **Full Name**   | Simple Network Management Protocol  | Windows Management Instrumentation   | Secure Shell                         | Hypertext Transfer Protocol          | Packet Internet Groper               |
| **Primary Use** | Network management and monitoring   | Management of Windows-based systems  | Secure remote command execution      | Web page transfer                    | Network connectivity testing         |
| **Protocol**    | UDP (mainly)                        | DCOM (Distributed Component Object Model) | TCP/IP                              | TCP/IP                               | ICMP                                 |
| **Security**    | SNMPv3 offers strong security       | Uses Windows authentication          | Strong encryption (SSH-2)            | Can use HTTPS for secure transactions | No encryption, vulnerable to DoS    |
| **Components**  | Managed devices, agents, NMS        | CIM, WMI providers                   | SSH client, SSH server               | Web client, web server               | Ping command, destination host       |
| **Data Format** | Structured data (MIBs)              | Structured data (CIM classes)        | Text-based command interface         | Text/HTML                            | Simple ICMP messages                 |
| **Example**     | Query router CPU usage              | Retrieve event logs from a Windows server | Remote login to a Linux server     | Retrieve a web page using a browser  | Check if a server is reachable       |

These protocols and tools serve different purposes, each suited to specific tasks in network management, remote administration, web services, and connectivity testing.

### Protocols in Details

#### SNMP

##### Usage of SNMP

1. **Monitoring Network Performance:**
   - SNMP allows network administrators to monitor the performance of network devices by collecting data on metrics such as CPU usage, memory usage, bandwidth utilization, and error rates.

2. **Fault Management:**
   - SNMP is used to detect and diagnose network faults. Devices can send SNMP traps to alert administrators of issues, such as link failures, high error rates, or hardware faults.

3. **Configuration Management:**
   - Administrators can use SNMP to configure network devices remotely. This includes setting parameters, updating firmware, and adjusting configurations as needed.

4. **Security Management:**
   - SNMP helps in managing network security by monitoring and controlling access to network resources, detecting unauthorized access attempts, and enforcing security policies.

5. **Inventory Management:**
   - SNMP can be used to collect information about network devices, such as hardware details, software versions, and installed modules, aiding in asset management.

##### Classification of SNMP

SNMP is classified into different versions and components, as well as various data types it handles. Here are the main classifications:

##### SNMP Versions:

1. **SNMPv1:**
   - The original version of SNMP, providing basic features for network management.
   - Uses community strings for authentication.

2. **SNMPv2c:**
   - An enhanced version of SNMPv1, offering improved performance and additional protocol operations.
   - Still uses community-based security similar to SNMPv1.

3. **SNMPv3:**
   - The most recent version, providing significant security enhancements, including authentication, encryption, and access control.
   - Supports user-based security model (USM) and view-based access control model (VACM).

##### SNMP Components:

1. **SNMP Manager:**
   - The central system that communicates with SNMP agents on network devices to collect and manage information.

2. **SNMP Agent:**
   - Software running on network devices that collects data and responds to requests from the SNMP manager.
   - Agents can also send traps to notify the manager of specific events.

3. **Management Information Base (MIB):**
   - A hierarchical database of network management information maintained by the SNMP agent.
   - Defines the structure and types of data that can be queried or set by the SNMP manager.

4. **SNMP Trap:**
   - Asynchronous notifications sent by SNMP agents to the SNMP manager to alert them of significant events or changes in status.

##### SNMP Data Types:

1. **Scalars:**
   - Single data points, such as system uptime or CPU load.

2. **Tables:**
   - Collections of related data points, such as a routing table or interface statistics.

3. **Objects:**
   - Defined entities within the MIB, each with a unique identifier (OID) used to query or set specific information.

Overall, SNMP is a vital protocol for network management, enabling administrators to monitor, manage, and ensure the health and performance of networked devices.

 OID - Object Identifier [Numerical Based]
 
 MIB - Management Information Base [ Numerical Based => text based]

#SNMP_Polling_And_SNMP_Trap
Sure, here's a table outlining the differences between polling and traps in SNMP:

| Feature                    | SNMP Polling                                     | SNMP Traps                                      |
|----------------------------|-------------------------------------------------|------------------------------------------------|
| **Definition**             | The NMS (Network Management System) requests data from managed devices at regular intervals. | Managed devices send unsolicited alerts to the NMS when specific events occur. |
| **Initiation**             | Initiated by the NMS.                           | Initiated by the managed device.                |
| **Communication**          | Periodic and continuous.                        | Event-driven and sporadic.                      |
| **Data Flow**              | Request/Response model.                         | One-way notification from the agent to the NMS. |
| **Network Traffic**        | Generates more network traffic due to frequent polling requests. | Generates less network traffic as traps are sent only when events occur. |
| **Resource Usage**         | Higher resource usage on both NMS and managed devices due to continuous polling. | Lower resource usage as traps are only sent when necessary. |
| **Timeliness**             | Potential delay in detecting events since data is only as current as the last poll. | Immediate notification of events, leading to faster response times. |
| **Reliability**            | More reliable for continuous monitoring since it regularly checks device status. | Less reliable for ongoing status checks as traps may be lost or not sent. |
| **Configuration**          | Requires setting up polling intervals and selecting specific data points to monitor. | Requires configuring devices to send traps and specifying trap conditions. |
| **Use Cases**              | Suitable for regular monitoring of performance metrics, such as CPU usage, memory, and interface statistics. | Suitable for alerting on specific events, such as link down, high CPU usage, or security breaches. |

Both polling and traps have their own advantages and are often used together in network management to provide comprehensive monitoring and alerting capabilities.


##### SNMP Python Code

Python code to extract CPU , Disk ,Memory Usage of the Systems
```python
import psutil

  

def get_system_resource_usage():

    """

    Gets CPU, disk, and memory usage using psutil.

  

    Returns:

        tuple: A tuple containing CPU percentage, disk usage percentage, and memory usage percentage.

    """

  

    # CPU usage

    cpu_percent = psutil.cpu_percent(interval=1)

  

    # Disk usage

    disk_partitions = psutil.disk_partitions()

    disk_usage = None

    for partition in disk_partitions:

        if partition.mountpoint == '/':  # Adjust for your desired disk

            disk_usage = psutil.disk_usage(partition.mountpoint)

            break

    if disk_usage:

        disk_percent = disk_usage.percent

    else:

        disk_percent = 0

  

    # Memory usage

    memory = psutil.virtual_memory()

    memory_percent = memory.percent

  

    return cpu_percent, disk_percent, memory_percent

  

# Example usage

cpu_usage, disk_usage, memory_usage = get_system_resource_usage()

print(f"CPU Usage: {cpu_usage}%")

print(f"Disk Usage: {disk_usage}%")

print(f"Memory Usage: {memory_usage}%")
```

#### WMI


#### SSH

#### HTTP


#### PING


## Tech Stack

| Tech                         | Useage |
| ---------------------------- | ------ |
| Python                       |        |
| Angular                      |        |
| NodeJS/Npm                   |        |
| Mongo DB                     |        |
| Postgre Sql                  |        |
| Kafka                        |        |
| RabbitMq                     |        |
| Redis                        |        |
| Nginx                        |        |
| Mobile Development Framework |        |





