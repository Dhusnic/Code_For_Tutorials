Certainly! Here's the information on CDP, CDP messages, CDP features, and LLDP commands presented in a table format.

### CDP Overview

CDP, or Cisco Discovery Protocol, is a proprietary Layer 2 protocol developed by Cisco Systems. Its primary function is to allow Cisco devices to discover and learn about neighboring Cisco devices directly connected to them on a network. Here's an overview of its key aspects:

1. **Discovery and Neighbor Information:** CDP helps Cisco devices discover and collect information about directly connected Cisco devices, such as routers, switches, access points, and IP phones.

2. **Protocol Operation:** CDP operates at Layer 2 of the OSI model, using multicast frames (specifically using Ethernet SNAP frames with a destination MAC address of 01:00:0c:cc:cc:cc) to communicate.

3. **Information Provided:** It provides information like device type (router, switch, etc.), IP addresses, platform details (such as model and software version), and port IDs (the interface through which CDP frames are exchanged).

4. **Use Cases:** CDP is useful for network administrators to quickly identify and troubleshoot connectivity issues, verify device connections, and gather inventory information about Cisco devices on the network.

5. **Configuration:** CDP is enabled by default on Cisco devices but can be globally disabled or configured per interface using commands like `no cdp run` (to disable globally) or `cdp enable` (to enable on an interface).

6. **Security Considerations:** While CDP provides valuable information for network management, it should be used with caution in untrusted environments due to potential security risks associated with exposing device details.

CDP is widely used within Cisco networks but is not interoperable with non-Cisco devices. Cisco has similar protocols like LLDP (Link Layer Discovery Protocol) that offer similar functionality and interoperability with other vendors' networking equipment.
### **CDP Messages with Timings and Contained Data**

| **Message Type**       | **Frequency**             | **Contained Data**                                   |
|------------------------|---------------------------|------------------------------------------------------|
| **Hello Messages**     | Every 60 seconds (default) | Device ID, IP Address, Port ID, Capabilities, Software Version, Platform, Native VLAN, Duplex Status, Power over Ethernet (PoE) capabilities |
| **Hold Time**          | 180 seconds (default)     | Time until the CDP entry is removed if no hello messages are received |
| **Advertisement**      | When the state changes     | Updates on device information like IP address, capabilities, etc. |
| **Checksum**           | Continuous monitoring      | Ensures the integrity of CDP information             |

### **CDP Features**

| **Feature**                             | **Description**                                                                              |
|-----------------------------------------|----------------------------------------------------------------------------------------------|
| **Device Discovery**                    | Automatically discovers devices on the network and learns about their capabilities.          |
| **Neighbor Information Collection**     | Gathers data about neighboring devices, such as IP address, device type, and software version. |
| **Network Management**                  | Assists in network troubleshooting by providing a detailed view of the network topology.      |
| **VLAN Management**                     | Helps in managing VLAN information between neighboring devices.                               |
| **Security**                            | Can be used to identify unauthorized devices on the network.                                  |
| **Power over Ethernet (PoE) Detection** | Identifies if a neighboring device supports PoE, enabling power management and control.       |
| **Native VLAN Identification**          | Identifies the native VLAN configured on the port.                                            |

### CDP Commands
Here’s a table summarizing CDP commands along with their uses, examples, and explanations:

| **Command**             | **Use**                                             | **Explanation**                                                                 | **Example**                      |
|-------------------------|-----------------------------------------------------|---------------------------------------------------------------------------------|----------------------------------|
| `cdp run`               | Enables CDP globally on the device.                 | Activates CDP across all interfaces on the device.                              | `Router(config)# cdp run`        |
| `no cdp run`            | Disables CDP globally on the device.                | Turns off CDP for the entire device.                                            | `Router(config)# no cdp run`     |
| `cdp enable`            | Enables CDP on a specific interface.                | Turns on CDP on the selected interface if CDP is globally enabled.              | `Router(config-if)# cdp enable`  |
| `no cdp enable`         | Disables CDP on a specific interface.               | Deactivates CDP on the selected interface while CDP remains enabled globally.   | `Router(config-if)# no cdp enable` |
| `show cdp`              | Displays CDP status on the device.                  | Provides information about the global CDP status and configuration.             | `Router# show cdp`               |
| `show cdp neighbors`    | Displays information about directly connected devices. | Shows details such as device ID, local interface, holdtime, and capabilities.   | `Router# show cdp neighbors`     |
| `show cdp neighbors detail` | Displays detailed information about CDP neighbors. | Includes additional details like IP addresses, platform, and software version.  | `Router# show cdp neighbors detail` |
| `show cdp entry <device-id>` | Displays information about a specific CDP neighbor. | Provides detailed information about a particular neighboring device.            | `Router# show cdp entry Switch1` |
| `cdp timer <seconds>`   | Sets the frequency of CDP updates sent by the device. | Determines how often the device sends CDP updates (default is 60 seconds).      | `Router(config)# cdp timer 30`   |
| `cdp holdtime <seconds>`| Sets the time a CDP advertisement is retained.      | Specifies how long a device should hold a CDP packet before discarding it (default is 180 seconds). | `Router(config)# cdp holdtime 120` |
| `cdp advertise-v2`      | Enables CDP version 2 advertisements.               | Allows the device to use CDP version 2, which provides additional features like support for native VLAN information. | `Router(config)# cdp advertise-v2` |
| `clear cdp counters`    | Resets the CDP traffic counters.                    | Clears the CDP traffic statistics on the device.                                | `Router# clear cdp counters`     |
| `clear cdp table`       | Clears the CDP table of all entries.                | Removes all current CDP neighbor entries from the device's CDP table.           | `Router# clear cdp table`        |

This table should help you understand the key CDP commands, their functions, and how to apply them on Cisco devices.