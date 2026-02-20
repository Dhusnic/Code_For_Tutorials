# Network Vendor Pattern Catalog

This catalog summarizes high-signal network log patterns used by `rules/services/network.yml`.
It prioritizes critical/error events and includes warning/info operational signals.

## Cisco IOS
- Critical/Error samples:
  - `%LINK-3-UPDOWN ... down`
  - `%LINEPROTO-5-UPDOWN ... down`
  - `%BGP-5-ADJCHANGE ... Down/Idle/hold time expired`
  - `%OSPF-5-ADJCHG ... FULL to DOWN`
  - `%SYS-2-MALLOCFAIL`
  - `CPUHOG`
- Warning samples:
  - `ERR_DISABLE`
  - `SEC_LOGIN ... LOGIN_FAILED`
- Info samples:
  - `%SYS-5-CONFIG_I`

## Cisco NX-OS
- Critical/Error samples:
  - `%ETHPORT-...-IF_DOWN_*`
  - `%VPC-... suspend/inconsistency/peer-link down`
  - `peer-keepalive ... failed/down`
  - `%BGP-...-ADJCHANGE ... Down`
  - `%OSPF-...-ADJCHG ... down`
  - `NVE ... peer down`
- Warning samples:
  - `%HSRP-...-STATECHANGE`
- Info samples:
  - `VSHD_SYSLOG_CONFIG_I`

## Juniper Junos
- Critical/Error samples:
  - `SNMP_TRAP_LINK_DOWN`
  - `RPD_BGP_NEIGHBOR_STATE_CHANGED ... Down/Idle`
  - `RPD_OSPF_NBRDOWN`
  - `RPD_BFD_SESSION_DOWN`
  - `UI_COMMIT ... failed/error/rollback`
  - `CHASSISD_* ALARM/FAIL`
- Warning samples:
  - `LOGIN_FAILED`
  - `LICENSE_* EXPIRE/INVALID`
- Info samples:
  - `UI_COMMIT_COMPLETED`

## Arista EOS
- Critical/Error samples:
  - `%LINEPROTO-*UPDOWN ... down`
  - `%LINK-*UPDOWN ... down`
  - `%BGP-*ADJCHANGE ... Down`
  - `BFD ... session down`
  - `MLAG ... peer-link down`
  - `daemon/agent crash`
  - `temperature/power/fan ... critical`
- Warning samples:
  - `SPANTREE/STP ... change/blocking`
- Info samples:
  - `configuration saved`

## Fortinet FortiOS
- Critical/Error samples:
  - `interface ... down`
  - `BGP/OSPF ... neighbor ... down`
  - `subtype="vpn" ... failed/down`
  - `logid="0100022011"` / `conserve mode`
  - `system reboot/kernel panic/watchdog`
- Warning samples:
  - `CPU usage high`
  - `memory usage high`
  - `action="deny"|"drop"|"blocked"`
  - `Administrator login failed`
- Info samples:
  - `Configuration changed`

## Check Point
- Critical/Error samples:
  - `action=Drop`
  - `vpn/ipsec/ike ... down/failed`
  - `policy install failed`
  - `ClusterXL ... member down/failover`
- Warning samples:
  - `action=Reject`
  - `cpLogExporter ... error/failed/disconnect`
- Info samples:
  - `policy installed successfully`

## Palo Alto PAN-OS
- Critical/Error samples:
  - `,TRAFFIC, ... deny/drop/reset-*`
  - `,THREAT, ... severity high/critical`
  - `,SYSTEM, ... ike/ipsec/tunnel ... down/failed`
  - `,CONFIG, ... failed/error/rollback`
- Warning samples:
  - `,SYSTEM, ... HA failover/state change`
  - `authentication failed/login failed`
- Info samples:
  - `,CONFIG, ... succeeded/completed`

## F5 BIG-IP
- Critical/Error samples:
  - `01010019:5: Caught signal`
  - `01010028 ... No members available`
  - `01070638:5 ... monitor status down`
  - `virtual server ... unavailable`
  - `memory allocation failed`
- Warning samples:
  - `config sync failed` / `failover error`
- Info samples:
  - `01070727:5 ... monitor status up`

## MikroTik RouterOS
- Critical/Error samples:
  - `interface/ether*/wlan* ... down`
  - `route,bgp ... down/idle`
  - `ipsec/ike ... failed/down`
  - `watchdog ... reboot`
- Warning samples:
  - `firewall ... drop`
  - `cpu/memory ... high/low`
  - `login failure/authentication failed`
- Info samples:
  - `system,info,account ... logged in`

