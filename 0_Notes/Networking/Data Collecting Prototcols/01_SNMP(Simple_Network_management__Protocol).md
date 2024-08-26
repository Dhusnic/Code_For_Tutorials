#### Install SNMP in Linux

for Debian based systems
```bash
sudo apt-get install snmp
```

for arch Linux based systems
```bash
sudo pacman -S net-snmp
```


### SNMP Walk
`snmpwalk` is a command-line utility that is commonly used for querying information from network devices via the Simple Network Management Protocol (SNMP). It’s part of the Net-SNMP suite, which is a set of tools and libraries for managing network devices. Here's a detailed explanation of `snmpwalk`, including its requirements and how it works:

#### What is `snmpwalk`?
- **Purpose**: `snmpwalk` retrieves a sequence of SNMP objects from a network device. It starts with a specified Object Identifier (OID) and queries all the subsequent OIDs until the end of the MIB (Management Information Base) tree is reached or the queried data returns no further results.
- **Use Case**: It's typically used to get a bulk of data from SNMP-enabled devices, such as routers, switches, servers, and other network equipment. For example, you might use `snmpwalk` to gather information about interface statistics, device status, or system information.

#### How `snmpwalk` Works:
1. **OID Tree**: SNMP organizes data into a tree structure where each node is identified by an OID. The OID is a series of numbers separated by dots (e.g., 1.3.6.1.2.1). Each number represents a branch in the tree.
2. **Starting Point**: `snmpwalk` starts querying the device from a specified OID. If no OID is provided, it starts at the root of the MIB tree.
3. **Iteration**: The tool then queries each subsequent OID in the tree, moving down the hierarchy, until it reaches the end or a specified stopping point.

#### Requirements for Using `snmpwalk`:
1. **SNMP-Enabled Device**: The target device must have SNMP enabled and properly configured. The device should be reachable over the network.
   
2. **SNMP Community String**: 
   - For SNMPv1 and SNMPv2c, a community string (which acts like a password) is required. The community string is used to authenticate the request.
   - Example: `public` (a common default community string).
   
3. **SNMP Version**: 
   - `snmpwalk` supports SNMPv1, SNMPv2c, and SNMPv3.
   - **SNMPv1 and SNMPv2c**: Use a community string for authentication.
   - **SNMPv3**: More secure; uses usernames, encryption, and authentication protocols.
   
4. **Net-SNMP Installed**: 
   - `snmpwalk` is part of the Net-SNMP suite. This needs to be installed on the system from which you are running the command.
   - **Installation Example on Ubuntu**: 
     ```bash
     sudo apt-get install snmp
     ```
   
5. **Network Connectivity**: Ensure that the device is reachable from the machine running `snmpwalk` over the network (pingable and SNMP port is open).

#### Basic `snmpwalk` Syntax:
```bash
snmpwalk -v <version> -c <community_string> <target_ip> <OID>
```
- `-v <version>`: Specifies the SNMP version (`1`, `2c`, or `3`).
- `-c <community_string>`: The SNMP community string (e.g., `public` for SNMPv1/v2c).
- `<target_ip>`: The IP address or hostname of the target device.
- `<OID>`: The starting OID (optional). If omitted, `snmpwalk` starts at the root of the tree.

#### Example Commands:
1. **SNMPv2c Example**:
   ```bash
   snmpwalk -v 2c -c public 192.168.1.1
   ```
   This command walks through the entire MIB of the device at `192.168.1.1` using the community string `public`.

2. **SNMPv3 Example**:
   ```bash
   snmpwalk -v 3 -u username -l authPriv -a MD5 -A authpass -x DES -X privpass 192.168.1.1
   ```
   This example uses SNMPv3 with a user named `username`, authentication protocol MD5 with password `authpass`, and encryption protocol DES with password `privpass`.

### Practical Use Cases:
- **Device Inventory**: Gather information about all interfaces, IP addresses, and running configurations of a network device.
- **Monitoring**: Retrieve statistics about traffic, errors, or device uptime.
- **Troubleshooting**: Analyse specific OIDs for potential issues on a network device.

#### Key Points:
- `snmpwalk` can generate a lot of output, depending on the device and OID.
- You can filter or limit the output by specifying a more specific OID.
- Understanding MIBs and OIDs is crucial for effectively using `snmpwalk`.

This should give you a comprehensive understanding of `snmpwalk` and how to use it effectively in a networking environment.

#### SNMP WALK Output Format
The `snmpwalk` command retrieves a series of SNMP objects from a device. The output is typically a list of OIDs and their corresponding values. Each line in the output represents a single OID and the data it holds. I'll explain a sample output line by line using the command you provided:

### Command:
```bash
snmpwalk -v 2c -c public 192.168.1.1
```
- **-v 2c**: Specifies the SNMP version (SNMPv2c in this case).
- **-c public**: Specifies the community string (`public` is a common default community string).
- **192.168.1.1**: The IP address of the target SNMP-enabled device.
 
### Sample Output:
```plaintext
IF-MIB::ifDescr.1 = STRING: "eth0"
IF-MIB::ifType.1 = INTEGER: ethernetCsmacd(6)
IF-MIB::ifMtu.1 = INTEGER: 1500
IF-MIB::ifSpeed.1 = Gauge32: 100000000
IF-MIB::ifPhysAddress.1 = STRING: 00:1A:2B:3C:4D:5E
IF-MIB::ifAdminStatus.1 = INTEGER: up(1)
IF-MIB::ifOperStatus.1 = INTEGER: up(1)
IF-MIB::ifHCInOctets.1 = Counter64: 1234567890
```

#### Line-by-Line Explanation:

1. **`IF-MIB::ifDescr.1 = STRING: "eth0"`**
   - **`IF-MIB::ifDescr.1`**: This OID is from the `IF-MIB` and refers to the description of the first network interface on the device. The `.1` at the end indicates that this is the first interface.
   - **`STRING: "eth0"`**: The data type is `STRING`, and the value is `"eth0"`, which is the name of the interface (common in Linux-based systems).

2. **`IF-MIB::ifType.1 = INTEGER: ethernetCsmacd(6)`**
   - **`IF-MIB::ifType.1`**: Refers to the type of the first interface.
   - **`INTEGER: ethernetCsmacd(6)`**: The data type is `INTEGER`, and the value `ethernetCsmacd(6)` indicates that this interface is an Ethernet interface using CSMA/CD (Carrier Sense Multiple Access with Collision Detection), which is typical for Ethernet networks.

3. **`IF-MIB::ifMtu.1 = INTEGER: 1500`**
   - **`IF-MIB::ifMtu.1`**: Refers to the Maximum Transmission Unit (MTU) of the first interface.
   - **`INTEGER: 1500`**: The MTU is 1500 bytes, which is the standard size for Ethernet frames.

4. **`IF-MIB::ifSpeed.1 = Gauge32: 100000000`**
   - **`IF-MIB::ifSpeed.1`**: Refers to the speed of the first interface.
   - **`Gauge32: 100000000`**: The data type is `Gauge32`, and the value `100000000` represents the interface speed in bits per second (bps). In this case, it’s 100 Mbps.

5. **`IF-MIB::ifPhysAddress.1 = STRING: 00:1A:2B:3C:4D:5E`**
   - **`IF-MIB::ifPhysAddress.1`**: Refers to the physical (MAC) address of the first interface.
   - **`STRING: 00:1A:2B:3C:4D:5E`**: The MAC address is `00:1A:2B:3C:4D:5E`, which uniquely identifies the network interface at the hardware level.

6. **`IF-MIB::ifAdminStatus.1 = INTEGER: up(1)`**
   - **`IF-MIB::ifAdminStatus.1`**: Refers to the administrative status of the first interface.
   - **`INTEGER: up(1)`**: The value `up(1)` indicates that the interface is administratively enabled or "up."

7. **`IF-MIB::ifOperStatus.1 = INTEGER: up(1)`**
   - **`IF-MIB::ifOperStatus.1`**: Refers to the operational status of the first interface.
   - **`INTEGER: up(1)`**: The value `up(1)` indicates that the interface is operationally active, meaning it is functioning correctly.

8. **`IF-MIB::ifHCInOctets.1 = Counter64: 1234567890`**
   - **`IF-MIB::ifHCInOctets.1`**: Refers to the number of octets (bytes) received on the first interface, using a high-capacity (64-bit) counter.
   - **`Counter64: 1234567890`**: The data type is `Counter64`, and the value `1234567890` represents the total number of bytes that have been received on the interface.

#### General Observations:
- **OID**: The `OID` or identifier (`IF-MIB::ifDescr.1`, `IF-MIB::ifSpeed.1`, etc.) is listed first in each line. This tells you which specific piece of information is being reported.
- **Data Type**: After the `OID`, the data type (`STRING`, `INTEGER`, `Gauge32`, `Counter64`, etc.) is given, which indicates the format of the value.
- **Value**: Finally, the actual value associated with the `OID` is presented. This is the data retrieved from the device, which you can use for monitoring or analysis.

#### Summary:
- **Network Interface Data**: This output provides information about a specific network interface on the device (e.g., `eth0`), including its type, speed, MAC address, status, and traffic statistics.
- **Usefulness**: The data can be used for troubleshooting network issues, monitoring interface performance, and ensuring that interfaces are operating correctly. For example, you could use `ifHCInOctets` to track traffic volume or `ifOperStatus` to confirm that an interface is up and running.

The `snmpwalk` output gives you a detailed, line-by-line snapshot of various parameters and statistics about network devices, making it a powerful tool for network management.
