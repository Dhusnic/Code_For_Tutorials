import subprocess
import os

def detect_service_name(proc):
    try:
        with open(f"/proc/{proc.pid}/cgroup") as f:
            for line in f:
                if ".service" in line:
                    return line.split("/")[-1].strip()
    except:
        return None

def patch_service(service_name, cmd):
    new_cmd = "opentelemetry-instrument " + " ".join(cmd)

    override = f'''
[Service]
ExecStart=
ExecStart={new_cmd}
'''

    path = f"/etc/systemd/system/{service_name}.d/override.conf"

    os.makedirs(os.path.dirname(path), exist_ok=True)

    with open(path, "w") as f:
        f.write(override)

    subprocess.run(["systemctl", "daemon-reexec"])
    subprocess.run(["systemctl", "daemon-reload"])
    subprocess.run(["systemctl", "restart", service_name])
