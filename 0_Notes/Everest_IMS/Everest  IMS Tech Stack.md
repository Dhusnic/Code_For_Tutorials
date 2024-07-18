Frontend - HTML , CSS , Angular
Backend - python
wrapper - Django
Testing - Cucumber

#data_collection
1. snmp - simple Network Management Protocol (cpu , disk ,memory utilizations)
2. wmi (windows management instrumentation) - wmi qery and get utilizations
3. ssh 

nms
lts

#SNMP-Simple_Network_Management_Protocol


### SNMP
#### What is SNMP?


**Simple Network Management Protocol (SNMP)** is a protocol used for network management. It provides a standardized framework for managing devices on IP networks. SNMP is widely used to monitor, manage, and control network devices like routers, switches, servers, printers, and other devices connected to the network.

#### Usage of SNMP

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

#### Classification of SNMP

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

#### SNMP Data Types:

1. **Scalars:**
   - Single data points, such as system uptime or CPU load.

2. **Tables:**
   - Collections of related data points, such as a routing table or interface statistics.

3. **Objects:**
   - Defined entities within the MIB, each with a unique identifier (OID) used to query or set specific information.

Overall, SNMP is a vital protocol for network management, enabling administrators to monitor, manage, and ensure the health and performance of networked devices.

#Notes_of_SNMP

 OID - Object Identifier [Numerical Based]
 
 MIB - Management Information Base [ Numerical Based => text based]

#SNMP_Polling_And_SNMP_Trap

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




|     |     |
| --- | --- |
|     |     |
