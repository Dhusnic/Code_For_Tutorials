import os

def build_env(config):
    env = os.environ.copy()
    env["OTEL_SERVICE_NAME"] = config["service_name"]
    env["OTEL_EXPORTER_OTLP_ENDPOINT"] = config["otel_endpoint"]
    env["OTEL_TRACES_EXPORTER"] = "otlp"
    return env
