import subprocess
import os
import base64


def generate_config(config):
    os.makedirs("collector", exist_ok=True)

    use_es = config.get("enable_elasticsearch", False)
    use_oo = config.get("enable_openobserve", False)

    exporters_yaml = ""
    trace_exporters = []
    log_exporters = []

    if use_es:
        es_auth = base64.b64encode(
            f"{config['es_username']}:{config['es_password']}".encode()
        ).decode()
        exporters_yaml += f'''  elasticsearch:
    endpoints: ["{config['elasticsearch_url']}"]
    headers:
      Authorization: "Basic {es_auth}"
    traces_index: "infraon-traces"

'''
        trace_exporters.append("elasticsearch")

    if use_oo:
        oo_auth = base64.b64encode(
            f"{config['oo_username']}:{config['oo_password']}".encode()
        ).decode()
        oo_endpoint = f"{config['openobserve_url']}/api/{config['oo_org']}"
        # Two exporter instances — same endpoint, different "stream-name" header —
        # since OpenObserve routes to a stream via that header, not the OTel signal type.
        exporters_yaml += f'''  otlphttp/oo_traces:
    endpoint: "{oo_endpoint}"
    headers:
      Authorization: "Basic {oo_auth}"
      stream-name: "{config['oo_trace_stream']}"

  otlphttp/oo_logs:
    endpoint: "{oo_endpoint}"
    headers:
      Authorization: "Basic {oo_auth}"
      stream-name: "{config['oo_log_stream']}"

'''
        trace_exporters.append("otlphttp/oo_traces")
        log_exporters.append("otlphttp/oo_logs")

    pipelines_yaml = f'''    traces:
      receivers: [otlp]
      processors: [batch]
      exporters: [{", ".join(trace_exporters)}]
'''
    if log_exporters:
        pipelines_yaml += f'''    logs:
      receivers: [otlp]
      processors: [batch]
      exporters: [{", ".join(log_exporters)}]
'''

    yaml = f'''
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317
      http:
        endpoint: 0.0.0.0:4318
        cors:
          allowed_origins:
            - "http://localhost:4300"
            - "http://127.0.0.1:4300"
          allowed_headers:
            - "*"

processors:
  batch:
    timeout: 5s
    send_batch_size: 1024

exporters:
{exporters_yaml}
service:
  telemetry:
    metrics:
      level: none
  pipelines:
{pipelines_yaml}'''

    with open("collector/otel.yaml", "w") as f:
        f.write(yaml)


def start_collector():
    print("Starting OpenTelemetry Collector...")

    subprocess.Popen(
        ["./bin/otelcol", "--config", "collector/otel.yaml"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )