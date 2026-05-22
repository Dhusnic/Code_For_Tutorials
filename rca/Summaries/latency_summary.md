```text
RCA Step Latency Report
=======================
Results file      : D:\Code for tutorials\rca\log_rca_engine\data\results\rca_results.json
Data source       : MongoDB (dhusnic_test_db.rca_results via mongosh)
Signalizing input : elasticsearch
Kafka topic       : linux-logs
Source index key  : source_rca_index
Source index fall.: linux-logs
Redis stream mode : on
Redis stream base : Rca:signalized_log_events:signal:<signal>
Correlation mode  : redis_stream
Correlation index : rca_correlated_incidents_current
Corr interval     : 35s
RCA reads index   : rca_correlated_incidents_current*
RCA results store : MongoDB dhusnic_test_db.rca_results, file ../data/results/rca_results.json
RCA records found : 4
Records selected  : 4
Records analyzed  : 4
Records skipped   : 0
Partial mode      : on
Latest-only mode  : on
Open-only mode    : off
Workflow note     : Signal stream entries are written to per-signal Redis streams using the base prefix Rca:signalized_log_events:signal:<signal>.
Workflow note     : Signalizing -> correlation latency is measured from source-doc signalized_at to correlation correlated_at; it includes Redis dwell time and the correlation scheduler wait.
Workflow note     : Redis publish time is not persisted as a standalone timestamp, so it is folded into the signalizing stage.
Note              : Primary RCA results file was empty, checking worker result files next.
Note              : Elasticsearch hydration resolved 6 doc/index timestamp entries.
Note              : Correlation incident hydration resolved 4 incident timestamp entries.

Step-wise summary
-----------------
Source log -> signalized doc  : 28.71 s average
Signalized doc -> incident    : 20.16 s average
Incident -> RCA result        : 15.18 s average
End-to-end total              : 1m 04.0s average
End-to-end median             : 51.31 s
Partial records               : 0

Per-incident latency
--------------------
S/N  Incident ID               Rule ID                       Status  Logs  Log->Signalized  Signalized->Inc  Inc->RCA  Total     Missing
---  ------------------------  ----------------------------  ------  ----  ---------------  ---------------  --------  --------  -------
1    8d969f9b70371b42e7681...  CORR_PROD_RABBITMQ_CONNEC...  open    1     29.75 s          47.09 s          29.79 s   1m 46.6s  -      
2    ff05153f3e666dad4afe8...  CORR_PROD_SYSTEM_RAID_DEG...  open    2     25.57 s          9.42 s           20.64 s   55.63 s   -      
3    f3059b872149b4e39c617...  CORR_PROD_RABBITMQ_CONNEC...  open    1     29.75 s          12.01 s          5.23 s    47.00 s   -      
4    97e2c0d491b72a1838544...  CORR_PROD_RABBITMQ_CONNEC...  open    1     29.75 s          12.11 s          5.06 s    46.93 s   -
```



# 7 signalizing instances,7 correlation instances, 1 log_rca_engine , 1 log_config_syncer, 30 minutes of run

```text
RCA Step Latency Report
=======================
Results file      : D:\Code for tutorials\rca\log_rca_engine\data\results\rca_results.json
Data source       : MongoDB (dhusnic_test_db.rca_results via mongosh)
Signalizing input : elasticsearch
Kafka topic       : linux-logs
Source index key  : source_rca_index
Source index fall.: linux-logs
Redis stream mode : on
Redis stream base : Rca:signalized_log_events:signal:<signal>
Correlation mode  : redis_stream
Correlation index : rca_correlated_incidents_current
Corr interval     : 35s
RCA reads index   : rca_correlated_incidents_current*
RCA results store : MongoDB dhusnic_test_db.rca_results, file ../data/results/rca_results.json
RCA records found : 27
Records selected  : 27
Records analyzed  : 27
Records skipped   : 0
Partial mode      : on
Selection mode    : per-signature
Open-only mode    : off
Workflow note     : Signal stream entries are written to per-signal Redis streams using the base prefix Rca:signalized_log_events:signal:<signal>.
Workflow note     : Signalizing -> correlation latency is measured from source-doc signalized_at to correlation correlated_at; it includes Redis dwell time and the correlation scheduler wait.
Workflow note     : Redis publish time is not persisted as a standalone timestamp, so it is folded into the signalizing stage.
Note              : Primary RCA results file was empty, checking worker result files next.
Note              : Latency is computed from the incident creation snapshot when trigger_* and first_* RCA fields are available; otherwise the report falls back to the latest RCA snapshot fields.
Note              : Elasticsearch hydration resolved 30 doc/index timestamp entries.
Note              : Correlation incident hydration resolved 11 incident timestamp entries.

Step-wise summary
-----------------
Source log -> signalized doc  : 26.07 s average
Signalized doc -> incident    : 3m 31.2s average
Incident -> RCA result        : 13.65 s average
End-to-end total              : 4m 10.9s average
End-to-end median             : 1m 37.0s
Partial records               : 0

Per-incident latency
--------------------
S/N  Incident ID               Rule ID                       Status   Logs  Log->Signalized  Signalized->Inc  Inc->RCA  Total      Missing
---  ------------------------  ----------------------------  -------  ----  ---------------  ---------------  --------  ---------  -------
1    8aed0009a9ff017ca6800...  CORR_PROD_RABBITMQ_CONNEC...  closed   1     27.41 s          25m 43.6s        12.58 s   26m 23.5s  -      
2    b74843eb2452d2bf433e9...  CORR_PROD_MONGODB_DOWN_TO...  open     3     33.98 s          8m 11.1s         4.64 s    8m 49.7s   -      
3    c39ffd02e39a0a27ebf44...  CORR_PROD_MONGODB_AUTH_TO...  open     5     33.99 s          7m 03.9s         4.60 s    7m 42.5s   -      
4    fcf569cadde0cec49a13b...  CORR_PROD_RABBITMQ_CONNEC...  closed   1     27.41 s          5m 56.7s         29.08 s   6m 53.2s   -      
5    9eff4fd9c6a94955acc72...  CORR_PROD_MONGODB_DOWN_TO...  closed   3     24.51 s          4m 35.3s         29.23 s   5m 29.1s   -      
6    9eff4fd9c6a94955acc72...  CORR_PROD_MONGODB_DOWN_TO...  updated  3     24.51 s          4m 35.3s         29.23 s   5m 29.1s   -      
7    9eff4fd9c6a94955acc72...  CORR_PROD_MONGODB_DOWN_TO...  updated  3     24.51 s          4m 35.3s         29.23 s   5m 29.1s   -      
8    9eff4fd9c6a94955acc72...  CORR_PROD_MONGODB_DOWN_TO...  updated  3     24.51 s          4m 35.3s         29.23 s   5m 29.1s   -      
9    9eff4fd9c6a94955acc72...  CORR_PROD_MONGODB_DOWN_TO...  updated  3     24.51 s          4m 35.3s         29.23 s   5m 29.1s   -      
10   9eff4fd9c6a94955acc72...  CORR_PROD_MONGODB_DOWN_TO...  closed   3     24.51 s          4m 35.3s         29.23 s   5m 29.1s   -      
11   aa722339fe9ac5f758015...  CORR_PROD_RABBITMQ_CONNEC...  closed   1     27.41 s          4m 38.1s         17.47 s   5m 23.0s   -      
12   3a9b203d32d1092c3693e...  CORR_PROD_RABBITMQ_CONNEC...  closed   1     27.41 s          2m 47.9s         7.35 s    3m 22.7s   -      
13   ff9c4cc5a606c7d8f0e68...  CORR_PROD_SYSTEM_RAID_DEG...  updated  2     25.52 s          1m 07.5s         4.04 s    1m 37.0s   -      
14   ff9c4cc5a606c7d8f0e68...  CORR_PROD_SYSTEM_RAID_DEG...  updated  2     25.52 s          1m 07.5s         4.04 s    1m 37.0s   -      
15   ff9c4cc5a606c7d8f0e68...  CORR_PROD_SYSTEM_RAID_DEG...  updated  2     25.52 s          1m 07.5s         4.04 s    1m 37.0s   -      
16   ff9c4cc5a606c7d8f0e68...  CORR_PROD_SYSTEM_RAID_DEG...  updated  2     25.52 s          1m 07.5s         4.04 s    1m 37.0s   -      
17   ff9c4cc5a606c7d8f0e68...  CORR_PROD_SYSTEM_RAID_DEG...  updated  2     25.52 s          1m 07.5s         4.04 s    1m 37.0s   -      
18   ff9c4cc5a606c7d8f0e68...  CORR_PROD_SYSTEM_RAID_DEG...  updated  2     25.52 s          1m 07.5s         4.04 s    1m 37.0s   -      
19   ff9c4cc5a606c7d8f0e68...  CORR_PROD_SYSTEM_RAID_DEG...  updated  2     25.52 s          1m 07.5s         4.04 s    1m 37.0s   -      
20   ff9c4cc5a606c7d8f0e68...  CORR_PROD_SYSTEM_RAID_DEG...  updated  2     25.52 s          1m 07.5s         4.04 s    1m 37.0s   -      
21   ff9c4cc5a606c7d8f0e68...  CORR_PROD_SYSTEM_RAID_DEG...  updated  2     25.52 s          1m 07.5s         4.04 s    1m 37.0s   -      
22   ff9c4cc5a606c7d8f0e68...  CORR_PROD_SYSTEM_RAID_DEG...  open     2     25.52 s          1m 07.5s         4.04 s    1m 37.0s   -      
23   037dc0ecabb81b5868c47...  CORR_PROD_NGINX_BACKEND_C...  open     1     23.03 s          1m 02.3s         2.82 s    1m 28.2s   -      
24   16a621de289352e44feed...  CORR_PROD_RABBITMQ_CONNEC...  open     1     27.41 s          16.64 s          30.49 s   1m 14.5s   -      
25   35e09a2b284e9c481e4d3...  CORR_PROD_MONGODB_AUTH_TO...  open     5     24.51 s          11.46 s          14.57 s   50.53 s    -  
```

# 7 signalizing instances,10 correlation instances, 1 log_rca_engine , 1 log_config_syncer, 30 minutes of run, with scheduler timing 10s to 90s in log_rca_engine

```txt
RCA Step Latency Report
=======================
Results file      : D:\Code for tutorials\rca\log_rca_engine\data\results\rca_results.json
Data source       : MongoDB (dhusnic_test_db.rca_results via mongosh)
Signalizing input : elasticsearch
Kafka topic       : linux-logs
Source index key  : source_rca_index
Source index fall.: linux-logs
Redis stream mode : on
Redis stream base : Rca:signalized_log_events:signal:<signal>
Correlation mode  : redis_stream
Correlation index : rca_correlated_incidents_current
Corr interval     : 35s
RCA reads index   : rca_correlated_incidents_current*
RCA results store : MongoDB dhusnic_test_db.rca_results, file ../data/results/rca_results.json
RCA records found : 44
Records selected  : 44
Records analyzed  : 44
Records skipped   : 0
Partial mode      : on
Selection mode    : per-signature
Open-only mode    : off
Workflow note     : Signal stream entries are written to per-signal Redis streams using the base prefix Rca:signalized_log_events:signal:<signal>.
Workflow note     : Signalizing -> correlation latency is measured from source-doc signalized_at to correlation correlated_at; it includes Redis dwell time and the correlation scheduler wait.
Workflow note     : Redis publish time is not persisted as a standalone timestamp, so it is folded into the signalizing stage.
Note              : Primary RCA results file was empty, checking worker result files next.
Note              : Latency is computed from the incident creation snapshot when trigger_* and first_* RCA fields are available; otherwise the report falls back to the latest RCA snapshot fields.
Note              : Elasticsearch hydration resolved 32 doc/index timestamp entries.
Note              : Correlation incident hydration resolved 16 incident timestamp entries.

Step-wise summary
-----------------
Source log -> signalized doc  : 51.87 s average
Signalized doc -> incident    : 3m 06.7s average
Incident -> RCA result        : 47.35 s average
End-to-end total              : 4m 46.0s average
End-to-end median             : 2m 40.6s
Partial records               : 0

Per-incident latency
--------------------
S/N  Incident ID               Rule ID                       Status   Logs  Log->Signalized  Signalized->Inc  Inc->RCA  Total      Missing
---  ------------------------  ----------------------------  -------  ----  ---------------  ---------------  --------  ---------  -------
1    b79cf40b39fe70c620106...  CORR_PROD_RABBITMQ_CONNEC...  closed   1     37.63 s          27m 36.4s        20.02 s   28m 34.0s  -      
2    e7ecf4fe3fa88ac5b57b3...  CORR_PROD_RABBITMQ_CONNEC...  closed   1     36.25 s          25m 24.5s        13.08 s   26m 13.8s  -      
3    852091ad5a6b3d32223d4...  CORR_PROD_RABBITMQ_CONNEC...  closed   1     37.63 s          14m 16.2s        7.26 s    15m 01.0s  -      
4    be6b969fd4a7e8d7ff12f...  CORR_PROD_RABBITMQ_CONNEC...  closed   1     37.63 s          12m 02.1s        10.13 s   12m 49.9s  -      
5    b2c02a16ced56eb9a47b8...  CORR_PROD_RABBITMQ_CONNEC...  closed   1     37.63 s          11m 32.5s        6.83 s    12m 17.0s  -      
6    5d8417407cc8c066b075d...  CORR_PROD_MONGODB_AUTH_TO...  closed   5     27.29 s          11m 07.8s        27.60 s   12m 02.7s  -      
7    a9b3971a78c9eeee0c40f...  CORR_PROD_RABBITMQ_CONNEC...  closed   1     37.63 s          10m 18.9s        21.92 s   11m 18.5s  -      
8    8e7772b02e694c9bf84de...  CORR_PROD_RABBITMQ_CONNEC...  closed   1     37.63 s          10m 07.2s        14.16 s   10m 58.9s  -      
9    b74e5d0e6f917e78d9cb0...  CORR_PROD_RABBITMQ_CONNEC...  closed   1     37.63 s          5m 24.0s         5.15 s    6m 06.8s   -      
10   b7b71265e150a475a7016...  CORR_PROD_NGINX_BACKEND_C...  updated  4     57.01 s          18.51 s          1m 37.2s  2m 52.8s   -      
11   b7b71265e150a475a7016...  CORR_PROD_NGINX_BACKEND_C...  updated  4     57.01 s          18.51 s          1m 37.2s  2m 52.8s   -      
12   b7b71265e150a475a7016...  CORR_PROD_NGINX_BACKEND_C...  updated  4     57.01 s          18.51 s          1m 37.2s  2m 52.8s   -      
13   b7b71265e150a475a7016...  CORR_PROD_NGINX_BACKEND_C...  closed   4     57.01 s          18.51 s          1m 37.2s  2m 52.8s   -      
14   7af207c0e86f195cf17b9...  CORR_PROD_MONGODB_DOWN_TO...  closed   3     57.01 s          15.87 s          1m 34.1s  2m 47.0s   -      
15   7af207c0e86f195cf17b9...  CORR_PROD_MONGODB_DOWN_TO...  updated  3     57.01 s          15.87 s          1m 34.1s  2m 47.0s   -      
16   7af207c0e86f195cf17b9...  CORR_PROD_MONGODB_DOWN_TO...  updated  3     57.01 s          15.87 s          1m 34.1s  2m 47.0s   -      
17   7af207c0e86f195cf17b9...  CORR_PROD_MONGODB_DOWN_TO...  closed   3     57.01 s          15.87 s          1m 34.1s  2m 47.0s   -      
18   7af207c0e86f195cf17b9...  CORR_PROD_MONGODB_DOWN_TO...  updated  3     57.01 s          15.87 s          1m 34.1s  2m 47.0s   -      
19   7af207c0e86f195cf17b9...  CORR_PROD_MONGODB_DOWN_TO...  updated  3     57.01 s          15.87 s          1m 34.1s  2m 47.0s   -      
20   7af207c0e86f195cf17b9...  CORR_PROD_MONGODB_DOWN_TO...  closed   3     57.01 s          15.87 s          1m 34.1s  2m 47.0s   -      
21   192398c47d8d1e31fdd58...  CORR_PROD_MONGODB_AUTH_TO...  open     5     57.01 s          18.51 s          1m 25.1s  2m 40.6s   -      
22   192398c47d8d1e31fdd58...  CORR_PROD_MONGODB_AUTH_TO...  closed   5     57.01 s          18.51 s          1m 25.1s  2m 40.6s   -      
23   192398c47d8d1e31fdd58...  CORR_PROD_MONGODB_AUTH_TO...  updated  5     57.01 s          18.51 s          1m 25.1s  2m 40.6s   -      
24   192398c47d8d1e31fdd58...  CORR_PROD_MONGODB_AUTH_TO...  updated  5     57.01 s          18.51 s          1m 25.1s  2m 40.6s   -      
25   192398c47d8d1e31fdd58...  CORR_PROD_MONGODB_AUTH_TO...  updated  5     57.01 s          18.51 s          1m 25.1s  2m 40.6s   -      
26   192398c47d8d1e31fdd58...  CORR_PROD_MONGODB_AUTH_TO...  updated  5     57.01 s          18.51 s          1m 25.1s  2m 40.6s   -      
27   192398c47d8d1e31fdd58...  CORR_PROD_MONGODB_AUTH_TO...  updated  5     57.01 s          18.51 s          1m 25.1s  2m 40.6s   -      
28   192398c47d8d1e31fdd58...  CORR_PROD_MONGODB_AUTH_TO...  open     5     57.01 s          18.51 s          1m 25.1s  2m 40.6s   -      
29   94ee16c8563eca847cb36...  CORR_PROD_RABBITMQ_CONNEC...  closed   1     37.63 s          32.65 s          15.13 s   1m 25.4s   -      
30   37f91ece83949cb3cfb79...  CORR_PROD_RABBITMQ_CONNEC...  closed   1     37.63 s          32.28 s          15.41 s   1m 25.3s   -      
31   37f91ece83949cb3cfb79...  CORR_PROD_RABBITMQ_CONNEC...  closed   1     37.63 s          32.28 s          15.41 s   1m 25.3s   -      
32   375bcadedc9df74c60dc6...  CORR_PROD_RABBITMQ_CONNEC...  closed   1     37.63 s          32.39 s          15.19 s   1m 25.2s   -      
33   864193c2528c99522f6a1...  CORR_PROD_SYSTEM_RAID_DEG...  updated  2     1m 00.1s         7.02 s           13.94 s   1m 21.1s   -      
34   864193c2528c99522f6a1...  CORR_PROD_SYSTEM_RAID_DEG...  updated  2     1m 00.1s         7.02 s           13.94 s   1m 21.1s   -      
35   864193c2528c99522f6a1...  CORR_PROD_SYSTEM_RAID_DEG...  updated  2     1m 00.1s         7.02 s           13.94 s   1m 21.1s   -      
36   864193c2528c99522f6a1...  CORR_PROD_SYSTEM_RAID_DEG...  updated  2     1m 00.1s         7.02 s           13.94 s   1m 21.1s   -      
37   864193c2528c99522f6a1...  CORR_PROD_SYSTEM_RAID_DEG...  open     2     1m 00.1s         7.02 s           13.94 s   1m 21.1s   -      
38   864193c2528c99522f6a1...  CORR_PROD_SYSTEM_RAID_DEG...  updated  2     1m 00.1s         7.02 s           13.94 s   1m 21.1s   -      
39   864193c2528c99522f6a1...  CORR_PROD_SYSTEM_RAID_DEG...  updated  2     1m 00.1s         7.02 s           13.94 s   1m 21.1s   -      
40   864193c2528c99522f6a1...  CORR_PROD_SYSTEM_RAID_DEG...  updated  2     1m 00.1s         7.02 s           13.94 s   1m 21.1s   -      
41   864193c2528c99522f6a1...  CORR_PROD_SYSTEM_RAID_DEG...  updated  2     1m 00.1s         7.02 s           13.94 s   1m 21.1s   -      
42   864193c2528c99522f6a1...  CORR_PROD_SYSTEM_RAID_DEG...  updated  2     1m 00.1s         7.02 s           13.94 s   1m 21.1s   -      
43   864193c2528c99522f6a1...  CORR_PROD_SYSTEM_RAID_DEG...  updated  2     1m 00.1s         7.02 s           13.94 s   1m 21.1s   -      
44   864193c2528c99522f6a1...  CORR_PROD_SYSTEM_RAID_DEG...  closed   2     1m 00.1s         7.02 s           13.94 s   1m 21.1s   -
```
# 7 signalizing instances,10 correlation instances, 1 log_rca_engine , 1 log_config_syncer, 30 minutes of run, with scheduler timing 30s and 90s

## Section 1

```text
RCA Step Latency Report
=======================
Results file      : D:\Code for tutorials\rca\log_rca_engine\data\results\rca_results.json
Data source       : MongoDB (dhusnic_test_db.rca_results via mongosh)
Signalizing input : elasticsearch
Kafka topic       : linux-logs
Source index key  : source_rca_index
Source index fall.: linux-logs
Redis stream mode : on
Redis stream base : Rca:signalized_log_events:signal:<signal>
Correlation mode  : redis_stream
Correlation index : rca_correlated_incidents_current
Corr interval     : 35s
RCA reads index   : rca_correlated_incidents_current*
RCA results store : MongoDB dhusnic_test_db.rca_results, file ../data/results/rca_results.json
RCA records found : 16
Records selected  : 16
Records analyzed  : 16
Records skipped   : 0
Partial mode      : on
Selection mode    : per-signature
Open-only mode    : off
Workflow note     : Signal stream entries are written to per-signal Redis streams using the base prefix Rca:signalized_log_events:signal:<signal>.
Workflow note     : Signalizing -> correlation latency is measured from source-doc signalized_at to correlation correlated_at; it includes Redis dwell time and the correlation scheduler wait.
Workflow note     : Redis publish time is not persisted as a standalone timestamp, so it is folded into the signalizing stage.
Note              : Primary RCA results file was empty, checking worker result files next.
Note              : Latency is computed from the incident creation snapshot when trigger_* and first_* RCA fields are available; otherwise the report falls back to the latest RCA snapshot fields.
Note              : Elasticsearch hydration resolved 20 doc/index timestamp entries.
Note              : Correlation incident hydration resolved 12 incident timestamp entries.

Step-wise summary
-----------------
Source log -> signalized doc  : 42.00 s average
Signalized doc -> incident    : 2m 36.2s average
Incident -> RCA result        : 23.24 s average
End-to-end total              : 3m 41.4s average
End-to-end median             : 1m 21.5s
Partial records               : 0

Per-incident latency
--------------------
S/N  Incident ID               Rule ID                       Status  Logs  Log->Signalized  Signalized->Inc  Inc->RCA  Total      Missing
---  ------------------------  ----------------------------  ------  ----  ---------------  ---------------  --------  ---------  -------
1    a43648d32fd3517f70950...  CORR_PROD_RABBITMQ_CONNEC...  open    1     48.14 s          13m 17.6s        27.15 s   14m 32.9s  -      
2    39f949db121b82d273308...  CORR_PROD_RABBITMQ_CONNEC...  closed  1     48.14 s          7m 55.2s         26.46 s   9m 09.8s   -      
3    45fbe33a7f145c333dd12...  CORR_PROD_RABBITMQ_CONNEC...  closed  1     48.14 s          5m 04.3s         27.01 s   6m 19.5s   -      
4    737c09a4d07542ba67be4...  CORR_PROD_RABBITMQ_CONNEC...  closed  1     48.14 s          5m 00.4s         803 ms    5m 49.3s   -      
5    c7c216c20d8fc72f6a34e...  CORR_PROD_RABBITMQ_CONNEC...  closed  1     48.14 s          4m 01.6s         29.50 s   5m 19.2s   -      
6    b2aef21a7e9a3f00799fa...  CORR_PROD_RABBITMQ_CONNEC...  closed  1     48.14 s          4m 00.3s         707 ms    4m 49.1s   -      
7    7f1d6b95fc6e99d424c71...  CORR_PROD_MONGODB_AUTH_TO...  open    5     34.71 s          29.08 s          21.26 s   1m 25.1s   -      
8    7f1d6b95fc6e99d424c71...  CORR_PROD_MONGODB_AUTH_TO...  closed  5     34.71 s          29.08 s          21.26 s   1m 25.1s   -      
9    fc0b6644cf28e57cc62c2...  CORR_PROD_RABBITMQ_CONNEC...  closed  1     41.96 s          3.72 s           32.30 s   1m 18.0s   -      
10   fc0b6644cf28e57cc62c2...  CORR_PROD_RABBITMQ_CONNEC...  open    1     41.96 s          3.72 s           32.30 s   1m 18.0s   -      
11   993eb2113442442280d43...  CORR_PROD_RABBITMQ_CONNEC...  open    1     48.14 s          949 ms           28.83 s   1m 17.9s   -      
12   3c5aafa18bfd181f312bb...  CORR_PROD_RABBITMQ_CONNEC...  closed  1     41.96 s          3.69 s           32.16 s   1m 17.8s   -      
13   3c5aafa18bfd181f312bb...  CORR_PROD_RABBITMQ_CONNEC...  open    1     41.96 s          3.69 s           32.16 s   1m 17.8s   -      
14   0b5109561ab88c49f25eb...  CORR_PROD_MONGODB_DOWN_TO...  open    3     34.71 s          29.36 s          12.00 s   1m 16.1s   -      
15   0b5109561ab88c49f25eb...  CORR_PROD_MONGODB_DOWN_TO...  closed  3     34.71 s          29.36 s          12.00 s   1m 16.1s   -      
16   ff67f0818cb5ae57a24e3...  CORR_PROD_SYSTEM_RAID_DEG...  open    2     28.31 s          7.15 s           35.93 s   1m 11.4s   -      
```
## Section 2

```text
(.venv) PS D:\Code for tutorials\rca\scripts> python report_rca_step_latency.py
RCA Step Latency Report
=======================
Results file      : D:\Code for tutorials\rca\log_rca_engine\data\results\rca_results.json
Data source       : MongoDB (dhusnic_test_db.rca_results via mongosh)
Signalizing input : elasticsearch
Kafka topic       : linux-logs
Source index key  : source_rca_index
Source index fall.: linux-logs
Redis stream mode : on
Redis stream base : Rca:signalized_log_events:signal:<signal>
Correlation mode  : redis_stream
Correlation index : rca_correlated_incidents_current
Corr interval     : 35s
RCA reads index   : rca_correlated_incidents_current*
RCA results store : MongoDB dhusnic_test_db.rca_results, file ../data/results/rca_results.json
RCA records found : 42
Records selected  : 42
Records analyzed  : 42
Records skipped   : 0
Partial mode      : on
Selection mode    : per-signature
Open-only mode    : off
Workflow note     : Signal stream entries are written to per-signal Redis streams using the base prefix Rca:signalized_log_events:signal:<signal>.
Workflow note     : Signalizing -> correlation latency is measured from source-doc signalized_at to correlation correlated_at; it includes Redis dwell time and the correlation scheduler wait.
Workflow note     : Redis publish time is not persisted as a standalone timestamp, so it is folded into the signalizing stage.
Note              : Primary RCA results file was empty, checking worker result files next.
Note              : Latency is computed from the incident creation snapshot when trigger_* and first_* RCA fields are available; otherwise the report falls back to the latest RCA snapshot fields.
Note              : Elasticsearch hydration resolved 14 doc/index timestamp entries.
Note              : Correlation incident hydration resolved 13 incident timestamp entries.

Step-wise summary
-----------------
Source log -> signalized doc  : 41.67 s average
Signalized doc -> incident    : 1m 45.3s average
Incident -> RCA result        : 1m 37.6s average
End-to-end total              : 4m 07.2s average
End-to-end median             : 1m 29.3s
Partial records               : 1

Per-incident latency
--------------------
S/N  Incident ID               Rule ID                       Status   Logs  Log->Signalized  Signalized->Inc  Inc->RCA   Total      Missing                    
---  ------------------------  ----------------------------  -------  ----  ---------------  ---------------  ---------  ---------  ---------------------------
1    429aa3c1d5cda592f4254...  CORR_PROD_RABBITMQ_CONNEC...  closed   1     51.43 s          27m 53.0s        10.88 s    28m 55.3s  -                          
2    3b00833098348d5d8dc43...  CORR_PROD_MONGODB_AUTH_TO...  updated  3     16.49 s          22.95 s          18m 05.2s  18m 44.6s  -                          
3    3b00833098348d5d8dc43...  CORR_PROD_MONGODB_AUTH_TO...  updated  3     16.49 s          22.95 s          16m 26.1s  17m 05.6s  -                          
4    3b00833098348d5d8dc43...  CORR_PROD_MONGODB_AUTH_TO...  updated  3     16.49 s          22.95 s          14m 47.1s  15m 26.6s  -                          
5    3b00833098348d5d8dc43...  CORR_PROD_MONGODB_AUTH_TO...  open     3     16.49 s          22.95 s          13m 08.0s  13m 47.4s  -                          
6    55d4ec265920cab3d9788...  CORR_PROD_RABBITMQ_CONNEC...  closed   1     51.43 s          12m 10.1s        31.54 s    13m 33.0s  -                          
7    f8c6d77a724d74c0ca56b...  CORR_PROD_RABBITMQ_CONNEC...  closed   1     51.43 s          5m 41.8s         3.71 s     6m 36.9s   -                          
8    d71f4842136cc0bf02334...  CORR_PROD_RABBITMQ_CONNEC...  closed   1     51.43 s          4m 09.4s         7.43 s     5m 08.3s   -                          
9    cb045ed68b9cbd13d2a97...  CORR_PROD_RABBITMQ_CONNEC...  closed   1     51.43 s          3m 08.0s         7.44 s     4m 06.9s   -                          
10   5483616136bdf263121d1...  CORR_PROD_RABBITMQ_CONNEC...  closed   1     51.43 s          3m 04.4s         2.14 s     3m 57.9s   -                          
11   e9d6deec74596544ef7f8...  CORR_PROD_RABBITMQ_CONNEC...  closed   1     51.43 s          29.93 s          11.07 s    1m 32.4s   -                          
12   ba931ecee137afddf1fb0...  CORR_PROD_RABBITMQ_CONNEC...  open     1     51.43 s          29.76 s          11.19 s    1m 32.4s   -                          
13   68b5cd7dfa0e1e789db46...  CORR_PROD_SYSTEM_RAID_DEG...  updated  2     1m 00.2s         25.40 s          3.68 s     1m 29.3s   -                          
14   68b5cd7dfa0e1e789db46...  CORR_PROD_SYSTEM_RAID_DEG...  updated  2     1m 00.2s         25.40 s          3.68 s     1m 29.3s   -                          
15   68b5cd7dfa0e1e789db46...  CORR_PROD_SYSTEM_RAID_DEG...  updated  2     1m 00.2s         25.40 s          3.68 s     1m 29.3s   -                          
16   68b5cd7dfa0e1e789db46...  CORR_PROD_SYSTEM_RAID_DEG...  updated  2     1m 00.2s         25.40 s          3.68 s     1m 29.3s   -                          
17   68b5cd7dfa0e1e789db46...  CORR_PROD_SYSTEM_RAID_DEG...  updated  2     1m 00.2s         25.40 s          3.68 s     1m 29.3s   -                          
18   68b5cd7dfa0e1e789db46...  CORR_PROD_SYSTEM_RAID_DEG...  updated  2     1m 00.2s         25.40 s          3.68 s     1m 29.3s   -                          
19   68b5cd7dfa0e1e789db46...  CORR_PROD_SYSTEM_RAID_DEG...  updated  2     1m 00.2s         25.40 s          3.68 s     1m 29.3s   -                          
20   68b5cd7dfa0e1e789db46...  CORR_PROD_SYSTEM_RAID_DEG...  updated  2     1m 00.2s         25.40 s          3.68 s     1m 29.3s   -                          
21   68b5cd7dfa0e1e789db46...  CORR_PROD_SYSTEM_RAID_DEG...  updated  2     1m 00.2s         25.40 s          3.68 s     1m 29.3s   -                          
22   68b5cd7dfa0e1e789db46...  CORR_PROD_SYSTEM_RAID_DEG...  updated  2     1m 00.2s         25.40 s          3.68 s     1m 29.3s   -                          
23   68b5cd7dfa0e1e789db46...  CORR_PROD_SYSTEM_RAID_DEG...  updated  2     1m 00.2s         25.40 s          3.68 s     1m 29.3s   -                          
24   68b5cd7dfa0e1e789db46...  CORR_PROD_SYSTEM_RAID_DEG...  updated  2     1m 00.2s         25.40 s          3.68 s     1m 29.3s   -                          
25   68b5cd7dfa0e1e789db46...  CORR_PROD_SYSTEM_RAID_DEG...  updated  2     1m 00.2s         25.40 s          3.68 s     1m 29.3s   -                          
26   68b5cd7dfa0e1e789db46...  CORR_PROD_SYSTEM_RAID_DEG...  updated  2     1m 00.2s         25.40 s          3.68 s     1m 29.3s   -                          
27   68b5cd7dfa0e1e789db46...  CORR_PROD_SYSTEM_RAID_DEG...  updated  2     1m 00.2s         25.40 s          3.68 s     1m 29.3s   -                          
28   68b5cd7dfa0e1e789db46...  CORR_PROD_SYSTEM_RAID_DEG...  updated  2     1m 00.2s         25.40 s          3.68 s     1m 29.3s   -                          
29   68b5cd7dfa0e1e789db46...  CORR_PROD_SYSTEM_RAID_DEG...  open     2     1m 00.2s         25.40 s          3.68 s     1m 29.3s   -                          
30   afde0a66f3b2d76919e17...  CORR_PROD_RABBITMQ_CONNEC...  closed   1     51.43 s          29.91 s          4.58 s     1m 25.9s   -                          
31   99eb1578f8586e5ceab5a...  CORR_PROD_NGINX_BACKEND_C...  updated  1     16.47 s          56.66 s          9.77 s     1m 22.9s   -                          
32   99eb1578f8586e5ceab5a...  CORR_PROD_NGINX_BACKEND_C...  updated  1     16.47 s          56.66 s          9.77 s     1m 22.9s   -                          
33   99eb1578f8586e5ceab5a...  CORR_PROD_NGINX_BACKEND_C...  updated  1     16.47 s          56.66 s          9.77 s     1m 22.9s   -                          
34   99eb1578f8586e5ceab5a...  CORR_PROD_NGINX_BACKEND_C...  open     1     16.47 s          56.66 s          9.77 s     1m 22.9s   -                          
35   99eb1578f8586e5ceab5a...  CORR_PROD_NGINX_BACKEND_C...  open     1     16.47 s          56.66 s          9.77 s     1m 22.9s   -                          
36   c5d13d85fc2dae0e2bd3c...  CORR_PROD_MONGODB_DOWN_TO...  closed   1     16.47 s          22.97 s          8.95 s     48.39 s    -                          
37   c5d13d85fc2dae0e2bd3c...  CORR_PROD_MONGODB_DOWN_TO...  updated  1     16.47 s          22.97 s          8.95 s     48.39 s    -                          
38   c5d13d85fc2dae0e2bd3c...  CORR_PROD_MONGODB_DOWN_TO...  open     1     16.47 s          22.97 s          8.95 s     48.39 s    -                          
39   c5d13d85fc2dae0e2bd3c...  CORR_PROD_MONGODB_DOWN_TO...  closed   1     16.47 s          22.97 s          8.95 s     48.39 s    -                          
40   c5d13d85fc2dae0e2bd3c...  CORR_PROD_MONGODB_DOWN_TO...  closed   1     16.47 s          22.97 s          8.95 s     48.39 s    -                          
41   c5d13d85fc2dae0e2bd3c...  CORR_PROD_MONGODB_DOWN_TO...  open     1     16.47 s          22.97 s          8.95 s     48.39 s    -                          
42   3b00833098348d5d8dc43...  CORR_PROD_MONGODB_AUTH_TO...  open     3     16.49 s          22.95 s          -          -          rca_generated_at/updated_at
```

## Section 3

```text
(.venv) PS D:\Code for tutorials\rca\scripts> python report_rca_step_latency.py
RCA Step Latency Report
=======================
Results file      : D:\Code for tutorials\rca\log_rca_engine\data\results\rca_results.json
Data source       : MongoDB (dhusnic_test_db.rca_results via mongosh)
Signalizing input : elasticsearch
Kafka topic       : linux-logs
Source index key  : source_rca_index
Source index fall.: linux-logs
Redis stream mode : on
Redis stream base : Rca:signalized_log_events:signal:<signal>
Correlation mode  : redis_stream
Correlation index : rca_correlated_incidents_current
Corr interval     : 35s
RCA reads index   : rca_correlated_incidents_current*
RCA results store : MongoDB dhusnic_test_db.rca_results, file ../data/results/rca_results.json
RCA records found : 63
Records selected  : 63
Records analyzed  : 63
Records skipped   : 0
Partial mode      : on
Selection mode    : per-signature
Open-only mode    : off
Workflow note     : Signal stream entries are written to per-signal Redis streams using the base prefix Rca:signalized_log_events:signal:<signal>.
Workflow note     : Signalizing -> correlation latency is measured from source-doc signalized_at to correlation correlated_at; it includes Redis dwell time and the correlation scheduler wait.
Workflow note     : Redis publish time is not persisted as a standalone timestamp, so it is folded into the signalizing stage.
Note              : Primary RCA results file was empty, checking worker result files next.
Note              : Latency is computed from the incident creation snapshot when trigger_* and first_* RCA fields are available; otherwise the report falls back to the latest RCA snapshot fields.
Note              : Elasticsearch hydration resolved 28 doc/index timestamp entries.
Note              : Correlation incident hydration resolved 16 incident timestamp entries.

Step-wise summary
-----------------
Source log -> signalized doc  : 39.81 s average
Signalized doc -> incident    : 2m 19.8s average
Incident -> RCA result        : 2m 35.7s average
End-to-end total              : 5m 37.5s average
End-to-end median             : 1m 29.3s
Partial records               : 1

Per-incident latency
--------------------
S/N  Incident ID               Rule ID                       Status   Logs  Log->Signalized  Signalized->Inc  Inc->RCA   Total      Missing                    
---  ------------------------  ----------------------------  -------  ----  ---------------  ---------------  ---------  ---------  ---------------------------
1    db8f6d900222d01ebd398...  CORR_PROD_RABBITMQ_CONNEC...  open     1     23.78 s          28m 33.5s        2.42 s     28m 59.7s  -                          
2    429aa3c1d5cda592f4254...  CORR_PROD_RABBITMQ_CONNEC...  closed   1     51.43 s          27m 53.0s        10.88 s    28m 55.3s  -                          
3    706863cbff47fd4f8ad67...  CORR_PROD_RABBITMQ_CONNEC...  closed   1     18.75 s          27m 39.3s        3.33 s     28m 01.4s  -                          
4    3b00833098348d5d8dc43...  CORR_PROD_MONGODB_AUTH_TO...  open     3     16.49 s          22.95 s          27m 14.4s  27m 53.8s  -                          
5    3b00833098348d5d8dc43...  CORR_PROD_MONGODB_AUTH_TO...  closed   3     16.49 s          22.95 s          23m 32.6s  24m 12.0s  -                          
6    3b00833098348d5d8dc43...  CORR_PROD_MONGODB_AUTH_TO...  updated  3     16.49 s          22.95 s          21m 16.0s  21m 55.5s  -                          
7    3b00833098348d5d8dc43...  CORR_PROD_MONGODB_AUTH_TO...  updated  3     16.49 s          22.95 s          20m 03.9s  20m 43.3s  -                          
8    3b00833098348d5d8dc43...  CORR_PROD_MONGODB_AUTH_TO...  updated  3     16.49 s          22.95 s          18m 05.2s  18m 44.6s  -                          
9    3b00833098348d5d8dc43...  CORR_PROD_MONGODB_AUTH_TO...  updated  3     16.49 s          22.95 s          16m 26.1s  17m 05.6s  -                          
10   3b00833098348d5d8dc43...  CORR_PROD_MONGODB_AUTH_TO...  updated  3     16.49 s          22.95 s          14m 47.1s  15m 26.6s  -                          
11   3b00833098348d5d8dc43...  CORR_PROD_MONGODB_AUTH_TO...  open     3     16.49 s          22.95 s          13m 08.0s  13m 47.4s  -                          
12   55d4ec265920cab3d9788...  CORR_PROD_RABBITMQ_CONNEC...  closed   1     51.43 s          12m 10.1s        31.54 s    13m 33.0s  -                          
13   ff99d2dbafb54f96e7821...  CORR_PROD_MONGODB_AUTH_TO...  closed   5     59.99 s          8m 08.8s         7.74 s     9m 16.5s   -                          
14   f8c6d77a724d74c0ca56b...  CORR_PROD_RABBITMQ_CONNEC...  closed   1     51.43 s          5m 41.8s         3.71 s     6m 36.9s   -                          
15   d71f4842136cc0bf02334...  CORR_PROD_RABBITMQ_CONNEC...  closed   1     51.43 s          4m 09.4s         7.43 s     5m 08.3s   -                          
16   cb045ed68b9cbd13d2a97...  CORR_PROD_RABBITMQ_CONNEC...  closed   1     51.43 s          3m 08.0s         7.44 s     4m 06.9s   -                          
17   5483616136bdf263121d1...  CORR_PROD_RABBITMQ_CONNEC...  closed   1     51.43 s          3m 04.4s         2.14 s     3m 57.9s   -                          
18   e9d6deec74596544ef7f8...  CORR_PROD_RABBITMQ_CONNEC...  open     1     51.43 s          29.93 s          11.07 s    1m 32.4s   -                          
19   e9d6deec74596544ef7f8...  CORR_PROD_RABBITMQ_CONNEC...  closed   1     51.43 s          29.93 s          11.07 s    1m 32.4s   -                          
20   e9d6deec74596544ef7f8...  CORR_PROD_RABBITMQ_CONNEC...  closed   1     51.43 s          29.93 s          11.07 s    1m 32.4s   -                          
21   ba931ecee137afddf1fb0...  CORR_PROD_RABBITMQ_CONNEC...  closed   1     51.43 s          29.76 s          11.19 s    1m 32.4s   -                          
22   ba931ecee137afddf1fb0...  CORR_PROD_RABBITMQ_CONNEC...  closed   1     51.43 s          29.76 s          11.19 s    1m 32.4s   -                          
23   ba931ecee137afddf1fb0...  CORR_PROD_RABBITMQ_CONNEC...  open     1     51.43 s          29.76 s          11.19 s    1m 32.4s   -                          
24   68b5cd7dfa0e1e789db46...  CORR_PROD_SYSTEM_RAID_DEG...  updated  2     1m 00.2s         25.40 s          3.68 s     1m 29.3s   -                          
25   68b5cd7dfa0e1e789db46...  CORR_PROD_SYSTEM_RAID_DEG...  updated  2     1m 00.2s         25.40 s          3.68 s     1m 29.3s   -                          
26   68b5cd7dfa0e1e789db46...  CORR_PROD_SYSTEM_RAID_DEG...  updated  2     1m 00.2s         25.40 s          3.68 s     1m 29.3s   -                          
27   68b5cd7dfa0e1e789db46...  CORR_PROD_SYSTEM_RAID_DEG...  updated  2     1m 00.2s         25.40 s          3.68 s     1m 29.3s   -                          
28   68b5cd7dfa0e1e789db46...  CORR_PROD_SYSTEM_RAID_DEG...  updated  2     1m 00.2s         25.40 s          3.68 s     1m 29.3s   -                          
29   68b5cd7dfa0e1e789db46...  CORR_PROD_SYSTEM_RAID_DEG...  updated  2     1m 00.2s         25.40 s          3.68 s     1m 29.3s   -                          
30   68b5cd7dfa0e1e789db46...  CORR_PROD_SYSTEM_RAID_DEG...  updated  2     1m 00.2s         25.40 s          3.68 s     1m 29.3s   -                          
31   68b5cd7dfa0e1e789db46...  CORR_PROD_SYSTEM_RAID_DEG...  updated  2     1m 00.2s         25.40 s          3.68 s     1m 29.3s   -                          
32   68b5cd7dfa0e1e789db46...  CORR_PROD_SYSTEM_RAID_DEG...  updated  2     1m 00.2s         25.40 s          3.68 s     1m 29.3s   -                          
33   68b5cd7dfa0e1e789db46...  CORR_PROD_SYSTEM_RAID_DEG...  updated  2     1m 00.2s         25.40 s          3.68 s     1m 29.3s   -                          
34   68b5cd7dfa0e1e789db46...  CORR_PROD_SYSTEM_RAID_DEG...  updated  2     1m 00.2s         25.40 s          3.68 s     1m 29.3s   -                          
35   68b5cd7dfa0e1e789db46...  CORR_PROD_SYSTEM_RAID_DEG...  updated  2     1m 00.2s         25.40 s          3.68 s     1m 29.3s   -                          
36   68b5cd7dfa0e1e789db46...  CORR_PROD_SYSTEM_RAID_DEG...  updated  2     1m 00.2s         25.40 s          3.68 s     1m 29.3s   -                          
37   68b5cd7dfa0e1e789db46...  CORR_PROD_SYSTEM_RAID_DEG...  updated  2     1m 00.2s         25.40 s          3.68 s     1m 29.3s   -                          
38   68b5cd7dfa0e1e789db46...  CORR_PROD_SYSTEM_RAID_DEG...  updated  2     1m 00.2s         25.40 s          3.68 s     1m 29.3s   -                          
39   68b5cd7dfa0e1e789db46...  CORR_PROD_SYSTEM_RAID_DEG...  updated  2     1m 00.2s         25.40 s          3.68 s     1m 29.3s   -                          
40   68b5cd7dfa0e1e789db46...  CORR_PROD_SYSTEM_RAID_DEG...  updated  2     1m 00.2s         25.40 s          3.68 s     1m 29.3s   -                          
41   68b5cd7dfa0e1e789db46...  CORR_PROD_SYSTEM_RAID_DEG...  updated  2     1m 00.2s         25.40 s          3.68 s     1m 29.3s   -                          
42   68b5cd7dfa0e1e789db46...  CORR_PROD_SYSTEM_RAID_DEG...  updated  2     1m 00.2s         25.40 s          3.68 s     1m 29.3s   -                          
43   68b5cd7dfa0e1e789db46...  CORR_PROD_SYSTEM_RAID_DEG...  updated  2     1m 00.2s         25.40 s          3.68 s     1m 29.3s   -                          
44   68b5cd7dfa0e1e789db46...  CORR_PROD_SYSTEM_RAID_DEG...  updated  2     1m 00.2s         25.40 s          3.68 s     1m 29.3s   -                          
45   68b5cd7dfa0e1e789db46...  CORR_PROD_SYSTEM_RAID_DEG...  open     2     1m 00.2s         25.40 s          3.68 s     1m 29.3s   -                          
46   afde0a66f3b2d76919e17...  CORR_PROD_RABBITMQ_CONNEC...  closed   1     51.43 s          29.91 s          4.58 s     1m 25.9s   -                          
47   99eb1578f8586e5ceab5a...  CORR_PROD_NGINX_BACKEND_C...  updated  1     16.47 s          56.66 s          9.77 s     1m 22.9s   -                          
48   99eb1578f8586e5ceab5a...  CORR_PROD_NGINX_BACKEND_C...  updated  1     16.47 s          56.66 s          9.77 s     1m 22.9s   -                          
49   99eb1578f8586e5ceab5a...  CORR_PROD_NGINX_BACKEND_C...  updated  1     16.47 s          56.66 s          9.77 s     1m 22.9s   -                          
50   99eb1578f8586e5ceab5a...  CORR_PROD_NGINX_BACKEND_C...  updated  1     16.47 s          56.66 s          9.77 s     1m 22.9s   -                          
51   99eb1578f8586e5ceab5a...  CORR_PROD_NGINX_BACKEND_C...  updated  1     16.47 s          56.66 s          9.77 s     1m 22.9s   -                          
52   99eb1578f8586e5ceab5a...  CORR_PROD_NGINX_BACKEND_C...  open     1     16.47 s          56.66 s          9.77 s     1m 22.9s   -                          
53   99eb1578f8586e5ceab5a...  CORR_PROD_NGINX_BACKEND_C...  open     1     16.47 s          56.66 s          9.77 s     1m 22.9s   -                          
54   c5d13d85fc2dae0e2bd3c...  CORR_PROD_MONGODB_DOWN_TO...  updated  1     16.47 s          22.97 s          8.95 s     48.39 s    -                          
55   c5d13d85fc2dae0e2bd3c...  CORR_PROD_MONGODB_DOWN_TO...  updated  1     16.47 s          22.97 s          8.95 s     48.39 s    -                          
56   c5d13d85fc2dae0e2bd3c...  CORR_PROD_MONGODB_DOWN_TO...  open     1     16.47 s          22.97 s          8.95 s     48.39 s    -                          
57   c5d13d85fc2dae0e2bd3c...  CORR_PROD_MONGODB_DOWN_TO...  closed   1     16.47 s          22.97 s          8.95 s     48.39 s    -                          
58   c5d13d85fc2dae0e2bd3c...  CORR_PROD_MONGODB_DOWN_TO...  updated  1     16.47 s          22.97 s          8.95 s     48.39 s    -                          
59   c5d13d85fc2dae0e2bd3c...  CORR_PROD_MONGODB_DOWN_TO...  open     1     16.47 s          22.97 s          8.95 s     48.39 s    -                          
60   c5d13d85fc2dae0e2bd3c...  CORR_PROD_MONGODB_DOWN_TO...  closed   1     16.47 s          22.97 s          8.95 s     48.39 s    -                          
61   c5d13d85fc2dae0e2bd3c...  CORR_PROD_MONGODB_DOWN_TO...  closed   1     16.47 s          22.97 s          8.95 s     48.39 s    -                          
62   c5d13d85fc2dae0e2bd3c...  CORR_PROD_MONGODB_DOWN_TO...  open     1     16.47 s          22.97 s          8.95 s     48.39 s    -                          
63   3b00833098348d5d8dc43...  CORR_PROD_MONGODB_AUTH_TO...  open     3     16.49 s          22.95 s          -          -          rca_generated_at/updated_at
```



# 10 signalizing instances,10 correlation instances, 10 log_rca_engine , 1 log_config_syncer, 30 minutes of run, with scheduler timing 30s and 90s

## Section 1

```text
(.venv) PS D:\Code for tutorials\rca\scripts> python .\report_rca_step_latency.py
RCA Step Latency Report
=======================
Results file      : D:\Code for tutorials\rca\log_rca_engine\data\results\rca_results.json
Data source       : MongoDB (dhusnic_test_db.rca_results via mongosh)
Signalizing input : elasticsearch
Kafka topic       : linux-logs
Source index key  : source_rca_index
Source index fall.: linux-logs
Redis stream mode : on
Redis stream base : Rca:signalized_log_events:signal:<signal>
Correlation mode  : redis_stream
Correlation index : rca_correlated_incidents_current
Corr interval     : 35s
RCA reads index   : rca_correlated_incidents_current*
RCA results store : MongoDB dhusnic_test_db.rca_results, file ../data/results/rca_results.json
RCA records found : 65
Records selected  : 65
Records analyzed  : 65
Records skipped   : 0
Partial mode      : on
Selection mode    : per-signature
Open-only mode    : off
Workflow note     : Signal stream entries are written to per-signal Redis streams using the base prefix Rca:signalized_log_events:signal:<signal>.
Workflow note     : Signalizing -> correlation latency is measured from source-doc signalized_at to correlation correlated_at; it includes Redis dwell time and the correlation scheduler wait.
Workflow note     : Redis publish time is not persisted as a standalone timestamp, so it is folded into the signalizing stage.
Note              : Primary RCA results file was empty, checking worker result files next.
Note              : Latency is computed from the incident creation snapshot when trigger_* and first_* RCA fields are available; otherwise the report falls back to the latest RCA snapshot fields.
Note              : Elasticsearch hydration resolved 18 doc/index timestamp entries.
Note              : Correlation incident hydration resolved 15 incident timestamp entries.

Step-wise summary
-----------------
Source log -> signalized doc  : 54.06 s average
Signalized doc -> incident    : 37.14 s average
Incident -> RCA result        : 21.68 s average
End-to-end total              : 1m 52.9s average
End-to-end median             : 1m 05.8s
Partial records               : 0

Per-incident latency
--------------------
S/N  Incident ID               Rule ID                       Status   Logs  Log->Signalized  Signalized->Inc  Inc->RCA   Total      Missing
---  ------------------------  ----------------------------  -------  ----  ---------------  ---------------  ---------  ---------  -------
1    85b2cd3c7b7dd78105d91...  CORR_PROD_RABBITMQ_CONNEC...  closed   1     25.14 s          15m 41.9s        1.93 s     16m 08.9s  -      
2    82c37db6bb13d3ad0ee6f...  CORR_PROD_RABBITMQ_CONNEC...  closed   1     25.14 s          2m 52.3s         10m 48.4s  14m 05.9s  -      
3    caf895ddd8a37b9866949...  CORR_PROD_RABBITMQ_CONNEC...  closed   1     25.14 s          4m 26.7s         816 ms     4m 52.6s   -      
4    1f7be76cd93cb1967b201...  CORR_PROD_RABBITMQ_CONNEC...  closed   1     25.14 s          3m 56.0s         3.26 s     4m 24.4s   -      
5    4a17067601146b13aa505...  CORR_PROD_RABBITMQ_CONNEC...  closed   1     25.14 s          2m 57.7s         9.19 s     3m 32.0s   -      
6    48cd31cfd4d7822f7e4f0...  CORR_PROD_RABBITMQ_CONNEC...  closed   1     25.14 s          2m 55.2s         1.51 s     3m 21.9s   -      
7    7d43461ffcddcac98afff...  CORR_PROD_RABBITMQ_CONNEC...  closed   1     25.14 s          2m 24.8s         1.92 s     2m 51.8s   -      
8    936d79c94813f1a230d01...  CORR_PROD_RABBITMQ_CONNEC...  closed   1     25.14 s          2m 24.6s         2.05 s     2m 51.8s   -      
9    716dc8073e9af0787d0f1...  CORR_PROD_NGINX_BACKEND_C...  updated  4     59.95 s          1.08 s           37.65 s    1m 38.7s   -      
10   716dc8073e9af0787d0f1...  CORR_PROD_NGINX_BACKEND_C...  open     4     59.95 s          1.08 s           37.65 s    1m 38.7s   -      
11   716dc8073e9af0787d0f1...  CORR_PROD_NGINX_BACKEND_C...  closed   4     59.95 s          1.08 s           37.65 s    1m 38.7s   -      
12   716dc8073e9af0787d0f1...  CORR_PROD_NGINX_BACKEND_C...  updated  4     59.95 s          1.08 s           37.65 s    1m 38.7s   -      
13   716dc8073e9af0787d0f1...  CORR_PROD_NGINX_BACKEND_C...  updated  4     59.95 s          1.08 s           37.65 s    1m 38.7s   -      
14   716dc8073e9af0787d0f1...  CORR_PROD_NGINX_BACKEND_C...  updated  4     59.95 s          1.08 s           37.65 s    1m 38.7s   -      
15   716dc8073e9af0787d0f1...  CORR_PROD_NGINX_BACKEND_C...  open     4     59.95 s          1.08 s           37.65 s    1m 38.7s   -      
16   0a1c33cbf20a4766a5556...  CORR_PROD_MONGODB_AUTH_TO...  open     5     59.95 s          1.25 s           32.48 s    1m 33.7s   -      
17   0a1c33cbf20a4766a5556...  CORR_PROD_MONGODB_AUTH_TO...  updated  5     59.95 s          1.25 s           32.48 s    1m 33.7s   -      
18   0a1c33cbf20a4766a5556...  CORR_PROD_MONGODB_AUTH_TO...  updated  5     59.95 s          1.25 s           32.48 s    1m 33.7s   -      
19   0a1c33cbf20a4766a5556...  CORR_PROD_MONGODB_AUTH_TO...  updated  5     59.95 s          1.25 s           32.48 s    1m 33.7s   -      
20   0a1c33cbf20a4766a5556...  CORR_PROD_MONGODB_AUTH_TO...  updated  5     59.95 s          1.25 s           32.48 s    1m 33.7s   -      
21   0a1c33cbf20a4766a5556...  CORR_PROD_MONGODB_AUTH_TO...  updated  5     59.95 s          1.25 s           32.48 s    1m 33.7s   -      
22   0a1c33cbf20a4766a5556...  CORR_PROD_MONGODB_AUTH_TO...  updated  5     59.95 s          1.25 s           32.48 s    1m 33.7s   -      
23   0a1c33cbf20a4766a5556...  CORR_PROD_MONGODB_AUTH_TO...  updated  5     59.95 s          1.25 s           32.48 s    1m 33.7s   -      
24   0a1c33cbf20a4766a5556...  CORR_PROD_MONGODB_AUTH_TO...  updated  5     59.95 s          1.25 s           32.48 s    1m 33.7s   -      
25   0a1c33cbf20a4766a5556...  CORR_PROD_MONGODB_AUTH_TO...  open     5     59.95 s          1.25 s           32.48 s    1m 33.7s   -      
26   d2c7457fc462785e3f1bc...  CORR_PROD_MONGODB_DOWN_TO...  updated  3     59.95 s          2.09 s           3.77 s     1m 05.8s   -      
27   d2c7457fc462785e3f1bc...  CORR_PROD_MONGODB_DOWN_TO...  updated  3     59.95 s          2.09 s           3.77 s     1m 05.8s   -      
28   d2c7457fc462785e3f1bc...  CORR_PROD_MONGODB_DOWN_TO...  updated  3     59.95 s          2.09 s           3.77 s     1m 05.8s   -      
29   d2c7457fc462785e3f1bc...  CORR_PROD_MONGODB_DOWN_TO...  updated  3     59.95 s          2.09 s           3.77 s     1m 05.8s   -      
30   d2c7457fc462785e3f1bc...  CORR_PROD_MONGODB_DOWN_TO...  updated  3     59.95 s          2.09 s           3.77 s     1m 05.8s   -      
31   d2c7457fc462785e3f1bc...  CORR_PROD_MONGODB_DOWN_TO...  open     3     59.95 s          2.09 s           3.77 s     1m 05.8s   -      
32   d2c7457fc462785e3f1bc...  CORR_PROD_MONGODB_DOWN_TO...  open     3     59.95 s          2.09 s           3.77 s     1m 05.8s   -      
33   d2c7457fc462785e3f1bc...  CORR_PROD_MONGODB_DOWN_TO...  updated  3     59.95 s          2.09 s           3.77 s     1m 05.8s   -      
34   d2c7457fc462785e3f1bc...  CORR_PROD_MONGODB_DOWN_TO...  updated  3     59.95 s          2.09 s           3.77 s     1m 05.8s   -      
35   d2c7457fc462785e3f1bc...  CORR_PROD_MONGODB_DOWN_TO...  updated  3     59.95 s          2.09 s           3.77 s     1m 05.8s   -      
36   d2c7457fc462785e3f1bc...  CORR_PROD_MONGODB_DOWN_TO...  updated  3     59.95 s          2.09 s           3.77 s     1m 05.8s   -      
37   d2c7457fc462785e3f1bc...  CORR_PROD_MONGODB_DOWN_TO...  updated  3     59.95 s          2.09 s           3.77 s     1m 05.8s   -      
38   d2c7457fc462785e3f1bc...  CORR_PROD_MONGODB_DOWN_TO...  open     3     59.95 s          2.09 s           3.77 s     1m 05.8s   -      
39   d2c7457fc462785e3f1bc...  CORR_PROD_MONGODB_DOWN_TO...  closed   3     59.95 s          2.09 s           3.77 s     1m 05.8s   -      
40   d2c7457fc462785e3f1bc...  CORR_PROD_MONGODB_DOWN_TO...  open     3     59.95 s          2.09 s           3.77 s     1m 05.8s   -      
41   d2c7457fc462785e3f1bc...  CORR_PROD_MONGODB_DOWN_TO...  closed   3     59.95 s          2.09 s           3.77 s     1m 05.8s   -      
42   b88b653ce0f4d619799c6...  CORR_PROD_SYSTEM_RAID_DEG...  updated  2     59.95 s          1.62 s           3.71 s     1m 05.3s   -      
43   b88b653ce0f4d619799c6...  CORR_PROD_SYSTEM_RAID_DEG...  updated  2     59.95 s          1.62 s           3.71 s     1m 05.3s   -      
44   b88b653ce0f4d619799c6...  CORR_PROD_SYSTEM_RAID_DEG...  updated  2     59.95 s          1.62 s           3.71 s     1m 05.3s   -      
45   b88b653ce0f4d619799c6...  CORR_PROD_SYSTEM_RAID_DEG...  updated  2     59.95 s          1.62 s           3.71 s     1m 05.3s   -      
46   b88b653ce0f4d619799c6...  CORR_PROD_SYSTEM_RAID_DEG...  updated  2     59.95 s          1.62 s           3.71 s     1m 05.3s   -      
47   b88b653ce0f4d619799c6...  CORR_PROD_SYSTEM_RAID_DEG...  updated  2     59.95 s          1.62 s           3.71 s     1m 05.3s   -      
48   b88b653ce0f4d619799c6...  CORR_PROD_SYSTEM_RAID_DEG...  updated  2     59.95 s          1.62 s           3.71 s     1m 05.3s   -      
49   b88b653ce0f4d619799c6...  CORR_PROD_SYSTEM_RAID_DEG...  updated  2     59.95 s          1.62 s           3.71 s     1m 05.3s   -      
50   b88b653ce0f4d619799c6...  CORR_PROD_SYSTEM_RAID_DEG...  updated  2     59.95 s          1.62 s           3.71 s     1m 05.3s   -      
51   b88b653ce0f4d619799c6...  CORR_PROD_SYSTEM_RAID_DEG...  updated  2     59.95 s          1.62 s           3.71 s     1m 05.3s   -      
52   b88b653ce0f4d619799c6...  CORR_PROD_SYSTEM_RAID_DEG...  updated  2     59.95 s          1.62 s           3.71 s     1m 05.3s   -      
53   b88b653ce0f4d619799c6...  CORR_PROD_SYSTEM_RAID_DEG...  updated  2     59.95 s          1.62 s           3.71 s     1m 05.3s   -      
54   b88b653ce0f4d619799c6...  CORR_PROD_SYSTEM_RAID_DEG...  updated  2     59.95 s          1.62 s           3.71 s     1m 05.3s   -      
55   b88b653ce0f4d619799c6...  CORR_PROD_SYSTEM_RAID_DEG...  updated  2     59.95 s          1.62 s           3.71 s     1m 05.3s   -      
56   b88b653ce0f4d619799c6...  CORR_PROD_SYSTEM_RAID_DEG...  updated  2     59.95 s          1.62 s           3.71 s     1m 05.3s   -      
57   b88b653ce0f4d619799c6...  CORR_PROD_SYSTEM_RAID_DEG...  updated  2     59.95 s          1.62 s           3.71 s     1m 05.3s   -      
58   b88b653ce0f4d619799c6...  CORR_PROD_SYSTEM_RAID_DEG...  updated  2     59.95 s          1.62 s           3.71 s     1m 05.3s   -      
59   b88b653ce0f4d619799c6...  CORR_PROD_SYSTEM_RAID_DEG...  updated  2     59.95 s          1.62 s           3.71 s     1m 05.3s   -      
60   b88b653ce0f4d619799c6...  CORR_PROD_SYSTEM_RAID_DEG...  updated  2     59.95 s          1.62 s           3.71 s     1m 05.3s   -      
61   b88b653ce0f4d619799c6...  CORR_PROD_SYSTEM_RAID_DEG...  open     2     59.95 s          1.62 s           3.71 s     1m 05.3s   -      
62   b88b653ce0f4d619799c6...  CORR_PROD_SYSTEM_RAID_DEG...  closed   2     59.95 s          1.62 s           3.71 s     1m 05.3s   -      
63   1648a0653c0be90088c07...  CORR_PROD_RABBITMQ_CONNEC...  closed   1     25.14 s          22.72 s          7.81 s     55.67 s    -      
64   b7d15704ade6b01d3d19a...  CORR_PROD_RABBITMQ_CONNEC...  closed   1     25.14 s          22.52 s          2.81 s     50.47 s    -      
65   4cd0f3e107cc0fe503f4e...  CORR_PROD_RABBITMQ_CONNEC...  closed   1     25.14 s          22.46 s          2.74 s     50.34 s    -  
```

## Section 2

```text
RCA Step Latency Report
=======================
Results file      : D:\Code for tutorials\rca\log_rca_engine\data\results\rca_results.json
Data source       : MongoDB (dhusnic_test_db.rca_results via mongosh)
Signalizing input : elasticsearch
Kafka topic       : linux-logs
Source index key  : source_rca_index
Source index fall.: linux-logs
Redis stream mode : on
Redis stream base : Rca:signalized_log_events:signal:<signal>
Correlation mode  : redis_stream
Correlation index : rca_correlated_incidents_current
Corr interval     : 35s
RCA reads index   : rca_correlated_incidents_current*
RCA results store : MongoDB dhusnic_test_db.rca_results, file ../data/results/rca_results.json
RCA records found : 67
Records selected  : 67
Records analyzed  : 67
Records skipped   : 0
Partial mode      : on
Selection mode    : per-signature
Open-only mode    : off
Workflow note     : Signal stream entries are written to per-signal Redis streams using the base prefix Rca:signalized_log_events:signal:<signal>.
Workflow note     : Signalizing -> correlation latency is measured from source-doc signalized_at to correlation correlated_at; it includes Redis dwell time and the correlation scheduler wait.
Workflow note     : Redis publish time is not persisted as a standalone timestamp, so it is folded into the signalizing stage.
Note              : Primary RCA results file was empty, checking worker result files next.
Note              : Latency is computed from the incident creation snapshot when trigger_* and first_* RCA fields are available; otherwise the report falls back to the latest RCA snapshot fields.
Note              : Elasticsearch hydration resolved 32 doc/index timestamp entries.
Note              : Correlation incident hydration resolved 9 incident timestamp entries.

Step-wise summary
-----------------
Source log -> signalized doc  : 37.47 s average
Signalized doc -> incident    : 1m 22.9s average
Incident -> RCA result        : 8.88 s average
End-to-end total              : 2m 09.3s average
End-to-end median             : 1m 20.0s
Partial records               : 0

Per-incident latency
--------------------
S/N  Incident ID               Rule ID                       Status   Logs  Log->Signalized  Signalized->Inc  Inc->RCA  Total      Missing
---  ------------------------  ----------------------------  -------  ----  ---------------  ---------------  --------  ---------  -------
1    eb4d3d086165709018228...  CORR_PROD_MONGODB_AUTH_TO...  closed   5     1m 02.3s         17m 16.0s        6.40 s    18m 24.7s  -      
2    eb4d3d086165709018228...  CORR_PROD_MONGODB_AUTH_TO...  closed   5     1m 02.3s         17m 16.0s        6.40 s    18m 24.7s  -      
3    278cc00caf898caf9890a...  CORR_PROD_NGINX_BACKEND_C...  closed   4     1m 00.1s         15m 33.3s        5.87 s    16m 39.3s  -      
4    278cc00caf898caf9890a...  CORR_PROD_NGINX_BACKEND_C...  closed   4     1m 00.1s         15m 33.3s        5.87 s    16m 39.3s  -      
5    18fbf06a95f93fb49f0bd...  CORR_PROD_SYSTEM_RAID_DEG...  updated  2     1m 00.2s         20.77 s          10.01 s   1m 31.0s   -      
6    18fbf06a95f93fb49f0bd...  CORR_PROD_SYSTEM_RAID_DEG...  updated  2     1m 00.2s         20.77 s          10.01 s   1m 31.0s   -      
7    18fbf06a95f93fb49f0bd...  CORR_PROD_SYSTEM_RAID_DEG...  updated  2     1m 00.2s         20.77 s          10.01 s   1m 31.0s   -      
8    18fbf06a95f93fb49f0bd...  CORR_PROD_SYSTEM_RAID_DEG...  updated  2     1m 00.2s         20.77 s          10.01 s   1m 31.0s   -      
9    18fbf06a95f93fb49f0bd...  CORR_PROD_SYSTEM_RAID_DEG...  updated  2     1m 00.2s         20.77 s          10.01 s   1m 31.0s   -      
10   18fbf06a95f93fb49f0bd...  CORR_PROD_SYSTEM_RAID_DEG...  updated  2     1m 00.2s         20.77 s          10.01 s   1m 31.0s   -      
11   18fbf06a95f93fb49f0bd...  CORR_PROD_SYSTEM_RAID_DEG...  updated  2     1m 00.2s         20.77 s          10.01 s   1m 31.0s   -      
12   18fbf06a95f93fb49f0bd...  CORR_PROD_SYSTEM_RAID_DEG...  updated  2     1m 00.2s         20.77 s          10.01 s   1m 31.0s   -      
13   18fbf06a95f93fb49f0bd...  CORR_PROD_SYSTEM_RAID_DEG...  updated  2     1m 00.2s         20.77 s          10.01 s   1m 31.0s   -      
14   18fbf06a95f93fb49f0bd...  CORR_PROD_SYSTEM_RAID_DEG...  updated  2     1m 00.2s         20.77 s          10.01 s   1m 31.0s   -      
15   18fbf06a95f93fb49f0bd...  CORR_PROD_SYSTEM_RAID_DEG...  updated  2     1m 00.2s         20.77 s          10.01 s   1m 31.0s   -      
16   18fbf06a95f93fb49f0bd...  CORR_PROD_SYSTEM_RAID_DEG...  updated  2     1m 00.2s         20.77 s          10.01 s   1m 31.0s   -      
17   18fbf06a95f93fb49f0bd...  CORR_PROD_SYSTEM_RAID_DEG...  updated  2     1m 00.2s         20.77 s          10.01 s   1m 31.0s   -      
18   18fbf06a95f93fb49f0bd...  CORR_PROD_SYSTEM_RAID_DEG...  updated  2     1m 00.2s         20.77 s          10.01 s   1m 31.0s   -      
19   18fbf06a95f93fb49f0bd...  CORR_PROD_SYSTEM_RAID_DEG...  updated  2     1m 00.2s         20.77 s          10.01 s   1m 31.0s   -      
20   18fbf06a95f93fb49f0bd...  CORR_PROD_SYSTEM_RAID_DEG...  open     2     1m 00.2s         20.77 s          10.01 s   1m 31.0s   -      
21   18fbf06a95f93fb49f0bd...  CORR_PROD_SYSTEM_RAID_DEG...  closed   2     1m 00.2s         20.77 s          10.01 s   1m 31.0s   -      
22   e709c4241573cb3cd4ea7...  CORR_PROD_RABBITMQ_CONNEC...  closed   1     37.33 s          32.26 s          10.49 s   1m 20.1s   -      
23   e709c4241573cb3cd4ea7...  CORR_PROD_RABBITMQ_CONNEC...  updated  1     37.33 s          32.26 s          10.49 s   1m 20.1s   -      
24   e709c4241573cb3cd4ea7...  CORR_PROD_RABBITMQ_CONNEC...  updated  1     37.33 s          32.26 s          10.49 s   1m 20.1s   -      
25   e709c4241573cb3cd4ea7...  CORR_PROD_RABBITMQ_CONNEC...  open     1     37.33 s          32.26 s          10.49 s   1m 20.1s   -      
26   e709c4241573cb3cd4ea7...  CORR_PROD_RABBITMQ_CONNEC...  open     1     37.33 s          32.26 s          10.49 s   1m 20.1s   -      
27   e709c4241573cb3cd4ea7...  CORR_PROD_RABBITMQ_CONNEC...  open     1     37.33 s          32.26 s          10.49 s   1m 20.1s   -      
28   e709c4241573cb3cd4ea7...  CORR_PROD_RABBITMQ_CONNEC...  open     1     37.33 s          32.26 s          10.49 s   1m 20.1s   -      
29   e3e61c9220549b31b7a9f...  CORR_PROD_RABBITMQ_CONNEC...  closed   1     37.33 s          32.09 s          10.60 s   1m 20.0s   -      
30   e3e61c9220549b31b7a9f...  CORR_PROD_RABBITMQ_CONNEC...  updated  1     37.33 s          32.09 s          10.60 s   1m 20.0s   -      
31   e3e61c9220549b31b7a9f...  CORR_PROD_RABBITMQ_CONNEC...  open     1     37.33 s          32.09 s          10.60 s   1m 20.0s   -      
32   e3e61c9220549b31b7a9f...  CORR_PROD_RABBITMQ_CONNEC...  closed   1     37.33 s          32.09 s          10.60 s   1m 20.0s   -      
33   e3e61c9220549b31b7a9f...  CORR_PROD_RABBITMQ_CONNEC...  updated  1     37.33 s          32.09 s          10.60 s   1m 20.0s   -      
34   e3e61c9220549b31b7a9f...  CORR_PROD_RABBITMQ_CONNEC...  open     1     37.33 s          32.09 s          10.60 s   1m 20.0s   -      
35   e3e61c9220549b31b7a9f...  CORR_PROD_RABBITMQ_CONNEC...  updated  1     37.33 s          32.09 s          10.60 s   1m 20.0s   -      
36   e3e61c9220549b31b7a9f...  CORR_PROD_RABBITMQ_CONNEC...  open     1     37.33 s          32.09 s          10.60 s   1m 20.0s   -      
37   e3e61c9220549b31b7a9f...  CORR_PROD_RABBITMQ_CONNEC...  open     1     37.33 s          32.09 s          10.60 s   1m 20.0s   -      
38   ae0d88928bdc946f57c22...  CORR_PROD_RABBITMQ_CONNEC...  updated  1     37.33 s          32.03 s          2.25 s    1m 11.6s   -      
39   ae0d88928bdc946f57c22...  CORR_PROD_RABBITMQ_CONNEC...  open     1     37.33 s          32.03 s          2.25 s    1m 11.6s   -      
40   ae0d88928bdc946f57c22...  CORR_PROD_RABBITMQ_CONNEC...  open     1     37.33 s          32.03 s          2.25 s    1m 11.6s   -      
41   ae0d88928bdc946f57c22...  CORR_PROD_RABBITMQ_CONNEC...  closed   1     37.33 s          32.03 s          2.25 s    1m 11.6s   -      
42   ae0d88928bdc946f57c22...  CORR_PROD_RABBITMQ_CONNEC...  open     1     37.33 s          32.03 s          2.25 s    1m 11.6s   -      
43   ae0d88928bdc946f57c22...  CORR_PROD_RABBITMQ_CONNEC...  updated  1     37.33 s          32.03 s          2.25 s    1m 11.6s   -      
44   ae0d88928bdc946f57c22...  CORR_PROD_RABBITMQ_CONNEC...  open     1     37.33 s          32.03 s          2.25 s    1m 11.6s   -      
45   ae0d88928bdc946f57c22...  CORR_PROD_RABBITMQ_CONNEC...  open     1     37.33 s          32.03 s          2.25 s    1m 11.6s   -      
46   bd5fbb12577f90ccbc492...  CORR_PROD_NGINX_BACKEND_C...  open     1     15.75 s          24.49 s          7.72 s    47.96 s    -      
47   bd5fbb12577f90ccbc492...  CORR_PROD_NGINX_BACKEND_C...  closed   1     15.75 s          24.49 s          7.72 s    47.96 s    -      
48   bd5fbb12577f90ccbc492...  CORR_PROD_NGINX_BACKEND_C...  closed   1     15.75 s          24.49 s          7.72 s    47.96 s    -      
49   bd5fbb12577f90ccbc492...  CORR_PROD_NGINX_BACKEND_C...  open     1     15.75 s          24.49 s          7.72 s    47.96 s    -      
50   bd5fbb12577f90ccbc492...  CORR_PROD_NGINX_BACKEND_C...  closed   1     15.75 s          24.49 s          7.72 s    47.96 s    -      
51   bd5fbb12577f90ccbc492...  CORR_PROD_NGINX_BACKEND_C...  open     1     15.75 s          24.49 s          7.72 s    47.96 s    -      
52   4dc216ec771acb4a38e92...  CORR_PROD_MONGODB_AUTH_TO...  closed   3     15.74 s          22.45 s          9.73 s    47.92 s    -      
53   4dc216ec771acb4a38e92...  CORR_PROD_MONGODB_AUTH_TO...  closed   3     15.74 s          22.45 s          9.73 s    47.92 s    -      
54   4dc216ec771acb4a38e92...  CORR_PROD_MONGODB_AUTH_TO...  closed   3     15.74 s          22.45 s          9.73 s    47.92 s    -      
55   4dc216ec771acb4a38e92...  CORR_PROD_MONGODB_AUTH_TO...  open     3     15.74 s          22.45 s          9.73 s    47.92 s    -      
56   4dc216ec771acb4a38e92...  CORR_PROD_MONGODB_AUTH_TO...  closed   3     15.74 s          22.45 s          9.73 s    47.92 s    -      
57   4dc216ec771acb4a38e92...  CORR_PROD_MONGODB_AUTH_TO...  open     3     15.74 s          22.45 s          9.73 s    47.92 s    -      
58   10481bc4c002ce4edbbc7...  CORR_PROD_MONGODB_DOWN_TO...  updated  1     15.75 s          21.31 s          10.85 s   47.91 s    -      
59   10481bc4c002ce4edbbc7...  CORR_PROD_MONGODB_DOWN_TO...  updated  1     15.75 s          21.31 s          10.85 s   47.91 s    -      
60   10481bc4c002ce4edbbc7...  CORR_PROD_MONGODB_DOWN_TO...  open     1     15.75 s          21.31 s          10.85 s   47.91 s    -      
61   10481bc4c002ce4edbbc7...  CORR_PROD_MONGODB_DOWN_TO...  closed   1     15.75 s          21.31 s          10.85 s   47.91 s    -      
62   10481bc4c002ce4edbbc7...  CORR_PROD_MONGODB_DOWN_TO...  updated  1     15.75 s          21.31 s          10.85 s   47.91 s    -      
63   10481bc4c002ce4edbbc7...  CORR_PROD_MONGODB_DOWN_TO...  updated  1     15.75 s          21.31 s          10.85 s   47.91 s    -      
64   10481bc4c002ce4edbbc7...  CORR_PROD_MONGODB_DOWN_TO...  updated  1     15.75 s          21.31 s          10.85 s   47.91 s    -      
65   10481bc4c002ce4edbbc7...  CORR_PROD_MONGODB_DOWN_TO...  updated  1     15.75 s          21.31 s          10.85 s   47.91 s    -      
66   10481bc4c002ce4edbbc7...  CORR_PROD_MONGODB_DOWN_TO...  open     1     15.75 s          21.31 s          10.85 s   47.91 s    -      
67   10481bc4c002ce4edbbc7...  CORR_PROD_MONGODB_DOWN_TO...  open     1     15.75 s          21.31 s          10.85 s   47.91 s    -      

```

## Section 4

```text
(.venv) PS D:\Code for tutorials\rca\scripts> python .\report_rca_step_latency.py
RCA Step Latency Report
=======================
Results file      : D:\Code for tutorials\rca\log_rca_engine\data\results\rca_results.json
Data source       : MongoDB (dhusnic_test_db.rca_results via mongosh)
Signalizing input : elasticsearch
Kafka topic       : linux-logs
Source index key  : source_rca_index
Source index fall.: linux-logs
Redis stream mode : on
Redis stream base : Rca:signalized_log_events:signal:<signal>
Correlation mode  : redis_stream
Correlation index : rca_correlated_incidents_current
Corr interval     : 35s
RCA reads index   : rca_correlated_incidents_current*
RCA results store : MongoDB dhusnic_test_db.rca_results, file ../data/results/rca_results.json
RCA records found : 25
Records selected  : 25
Records analyzed  : 25
Records skipped   : 0
Partial mode      : on
Selection mode    : per-signature
Open-only mode    : off
Workflow note     : Signal stream entries are written to per-signal Redis streams using the base prefix Rca:signalized_log_events:signal:<signal>.
Workflow note     : Signalizing -> correlation latency is measured from source-doc signalized_at to correlation correlated_at; it includes Redis dwell time and the correlation scheduler wait.
Workflow note     : Redis publish time is not persisted as a standalone timestamp, so it is folded into the signalizing stage.
Note              : Primary RCA results file was empty, checking worker result files next.
Note              : Latency is computed from the incident creation snapshot when trigger_* and first_* RCA fields are available; otherwise the report falls back to the latest RCA snapshot fields.
Note              : Elasticsearch hydration resolved 30 doc/index timestamp entries.
Note              : Correlation incident hydration resolved 8 incident timestamp entries.

Step-wise summary
-----------------
Source log -> signalized doc  : 54.27 s average
Signalized doc -> incident    : 21.06 s average
Incident -> RCA result        : 7.69 s average
End-to-end total              : 1m 23.0s average
End-to-end median             : 1m 18.7s
Partial records               : 0

Per-incident latency
--------------------
S/N  Incident ID               Rule ID                       Status   Logs  Log->Signalized  Signalized->Inc  Inc->RCA  Total     Missing
---  ------------------------  ----------------------------  -------  ----  ---------------  ---------------  --------  --------  -------
1    3fee08356c52b11a8e681...  CORR_PROD_MONGODB_AUTH_TO...  open     5     17.38 s          1m 35.9s         37.81 s   2m 31.1s  -      
2    d8a7362339f28e650b2f7...  CORR_PROD_SYSTEM_RAID_DEG...  updated  2     1m 00.2s         29.20 s          6.75 s    1m 36.1s  -      
3    d8a7362339f28e650b2f7...  CORR_PROD_SYSTEM_RAID_DEG...  updated  2     1m 00.2s         29.20 s          6.75 s    1m 36.1s  -      
4    d8a7362339f28e650b2f7...  CORR_PROD_SYSTEM_RAID_DEG...  updated  2     1m 00.2s         29.20 s          6.75 s    1m 36.1s  -      
5    d8a7362339f28e650b2f7...  CORR_PROD_SYSTEM_RAID_DEG...  updated  2     1m 00.2s         29.20 s          6.75 s    1m 36.1s  -      
6    d8a7362339f28e650b2f7...  CORR_PROD_SYSTEM_RAID_DEG...  updated  2     1m 00.2s         29.20 s          6.75 s    1m 36.1s  -      
7    d8a7362339f28e650b2f7...  CORR_PROD_SYSTEM_RAID_DEG...  updated  2     1m 00.2s         29.20 s          6.75 s    1m 36.1s  -      
8    d8a7362339f28e650b2f7...  CORR_PROD_SYSTEM_RAID_DEG...  updated  2     1m 00.2s         29.20 s          6.75 s    1m 36.1s  -      
9    d8a7362339f28e650b2f7...  CORR_PROD_SYSTEM_RAID_DEG...  updated  2     1m 00.2s         29.20 s          6.75 s    1m 36.1s  -      
10   d8a7362339f28e650b2f7...  CORR_PROD_SYSTEM_RAID_DEG...  open     2     1m 00.2s         29.20 s          6.75 s    1m 36.1s  -      
11   9058bee93fda17676596d...  CORR_PROD_NGINX_BACKEND_C...  updated  4     1m 00.1s         17.03 s          10.34 s   1m 27.5s  -      
12   9058bee93fda17676596d...  CORR_PROD_NGINX_BACKEND_C...  open     4     1m 00.1s         17.03 s          10.34 s   1m 27.5s  -      
13   d656e1fea78ad5c1b391f...  CORR_PROD_MONGODB_AUTH_TO...  open     5     1m 00.1s         12.28 s          6.29 s    1m 18.7s  -      
14   d656e1fea78ad5c1b391f...  CORR_PROD_MONGODB_AUTH_TO...  closed   5     1m 00.1s         12.28 s          6.29 s    1m 18.7s  -      
15   d656e1fea78ad5c1b391f...  CORR_PROD_MONGODB_AUTH_TO...  updated  5     1m 00.1s         12.28 s          6.29 s    1m 18.7s  -      
16   d656e1fea78ad5c1b391f...  CORR_PROD_MONGODB_AUTH_TO...  updated  5     1m 00.1s         12.28 s          6.29 s    1m 18.7s  -      
17   d656e1fea78ad5c1b391f...  CORR_PROD_MONGODB_AUTH_TO...  open     5     1m 00.1s         12.28 s          6.29 s    1m 18.7s  -      
18   8571406ba46dfdf95194b...  CORR_PROD_MONGODB_DOWN_TO...  open     3     1m 00.1s         11.40 s          5.89 s    1m 17.4s  -      
19   8571406ba46dfdf95194b...  CORR_PROD_MONGODB_DOWN_TO...  closed   3     1m 00.1s         11.40 s          5.89 s    1m 17.4s  -      
20   8571406ba46dfdf95194b...  CORR_PROD_MONGODB_DOWN_TO...  updated  3     1m 00.1s         11.40 s          5.89 s    1m 17.4s  -      
21   8571406ba46dfdf95194b...  CORR_PROD_MONGODB_DOWN_TO...  updated  3     1m 00.1s         11.40 s          5.89 s    1m 17.4s  -      
22   8571406ba46dfdf95194b...  CORR_PROD_MONGODB_DOWN_TO...  open     3     1m 00.1s         11.40 s          5.89 s    1m 17.4s  -      
23   8749a5bd87f493fa00d51...  CORR_PROD_RABBITMQ_CONNEC...  open     1     25.40 s          5.03 s           4.09 s    34.52 s   -      
24   dc883af2932ca84253dee...  CORR_PROD_RABBITMQ_CONNEC...  open     1     25.40 s          5.56 s           3.55 s    34.52 s   -      
25   3f212732f6e2236a02149...  CORR_PROD_RABBITMQ_CONNEC...  open     1     25.40 s          4.83 s           4.28 s    34.52 s   -     
```