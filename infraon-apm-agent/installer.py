import subprocess

def install_dependencies(python_path):
    packages = [
        "opentelemetry-distro",
        "opentelemetry-exporter-otlp",
        "opentelemetry-instrumentation-django",
        "opentelemetry-instrumentation-psycopg2"
    ]
    subprocess.run([python_path, "-m", "pip", "install"] + packages)
