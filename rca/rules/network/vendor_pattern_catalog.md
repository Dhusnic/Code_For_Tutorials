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

## HPE Aruba Networking (AOS-Switch / AOS-CX)
- Critical/Error samples:
  - `<peer-ip>: Peer down. error-code: ... vrf-name: ...`
  - `BGP: Peer down`
  - `BGP: Peer interface ... down`
  - `BGP: ... Peer Ideled`
  - `port ... is now off-line`
  - `Link status for interface ... is down`
  - `Fan ... Failure` / `Power Supply ... Failure`
  - `Over-temperature for sensor ...`
  - `PSU ... has shutdown due to over temperature`
- Warning samples:
  - `BFD session is down`
  - `Partner is out of sync ... LAG`
  - `Partner is lost (timed out) ... LAG`
  - `Port ... disabled - BPDU received on protected port`
  - `AdjChg: Nbr ... -> ...`
  - `ADJCHG: Neighbor ... moved ...`
  - `Dynamic LACP trunk ... is now off-line`
  - `Starved for a BPDU on port` / `Root changed from ...` / `Topology change ...`
  - `Event|13002|LOG_ERR|CDTR|... session has failed`
  - `Event|4640|LOG_ERR|AMM|... Failed to connect to Aruba Central/HPE Aruba Networking Central`
- Info samples:
  - `Module rebooted. Reason ...`

## Huawei VRP / CloudEngine / NetEngine
- Critical/Error samples:
  - `%%01IFNET/4/IF_STATE ... DOWN`
  - `%%01BGP/3/STATE_CHG_UPDOWN ... changed from Established to Idle/Active`
  - `%%01BFD/4/STACHG_TODWN`
  - `%%01OSPF/4/NBR_CHANGE_E ... NbrEvent=7/9/12`
  - `%%01MSTP/4/BPDU_PROTECTION`
  - `%%01ALML/4/POWERINVALID`
  - `%%01ENTITYTRAP/4/ENTITYBRDTEMPALARM`
- Warning samples:
  - `%%01VRRP/4/STATEWARNINGEXTEND` / `vrrpTrapNonMaster`
  - `%%01LACP/3/LAG_DOWN_REASON_EVENT`
  - `%%01MSTP/4/ROOT_LOST` / `RECEIVE_MSTITC`
  - `%%01VOSCPU/4/CPU_USAGE_HIGH`
  - `%%01SSH/4/SSH_FAIL`
- Info samples:
  - `%%01SHELL/5/CMDRECORD`

## Dell SmartFabric OS10 (PowerSwitch)
- Critical/Error samples:
  - `%BGP_NBR_BKWD_STATE_CHG`
  - `%VLT_VLTi_LINK_DOWN`
  - `%VLT_PEER_DOWN`
  - `%VLT_PORT_CHANNEL_DOWN`
  - `%STP_BPDU_GUARD_ERR`
  - `%EQM_UNIT_DOWN`
  - `%EQM_FAN_TRAY_OFF`
  - `%EQM_TML_MAJOR_CROSSED` / `%EQM_TML_CRIT_CROSSED`
- Warning samples:
  - `%BFD_STATE_CHANGE ... down/timeout`
  - `%OSPFV2_NBR_ADMN_DWN`
  - `%UFD_ERROR_SET` / `%UFD_GRP_ERROR_SET`
  - `%VLT_SOFTWARE_VERSION_MISMATCH`
  - `%VLT_ACL_ERROR`
  - `%ETL_HOST_UNREACHABLE`
  - `%IFM_OSTATE_DN`
- Info samples:
  - `%BGP_NBR_NOTIFY_EST_STATE`
  - `%USER_ROLE_CHANGE`

## CRON / Crontab (Linux-based network appliances)
- Critical/Error samples:
  - `(CRON) ... can't fork`
  - `do_command:setgid(...) failed`
  - `do_command:setuid(...) failed`
  - `do_command:initgroups(...) failed`
  - `errors in crontab file, can't install`
- Warning samples:
  - `No MTA installed, discarding output`
  - `"...":<line>: bad minute|bad hour|bad day-of-month|bad month|bad day-of-week`
  - `ERROR (Missing newline before EOF, this crontab file will be ignored)`
- Info samples:
  - `CRON[pid]: (user) CMD (...)`
  - `CRON[pid]: (user) END (...)`
  - `pam_unix(cron:session): session opened/closed ...`

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
