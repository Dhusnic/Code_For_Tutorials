#!/usr/bin/env python3

from config import CONFIG
from installer import install_dependencies
from detector import detect_runtime, get_python_path, is_systemd
from injector import build_env
from restart_manager import restart_process
from systemd_manager import detect_service_name, patch_service
from collector_manager import generate_config, start_collector

def main():
    print("Infraon Agent Starting...")

    runtime, proc, cmd = detect_runtime()

    if not runtime:
        print("No Django detected")
        return

    python_path = get_python_path(cmd)

    install_dependencies(python_path)

    generate_config(CONFIG)
    start_collector()

    if is_systemd(proc):
        service_name = detect_service_name(proc)
        if service_name:
            patch_service(service_name, cmd)
    else:
        env = build_env(CONFIG)
        restart_process(proc, cmd, env)

    print("Tracing enabled")

if __name__ == "__main__":
    main()
