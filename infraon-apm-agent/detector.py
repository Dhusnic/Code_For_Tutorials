import psutil

def detect_runtime():
    for proc in psutil.process_iter(['pid', 'cmdline']):
        cmd = proc.info['cmdline'] or []
        cmd_str = " ".join(cmd)

        if "gunicorn" in cmd_str:
            return ("gunicorn", proc, cmd)
        elif "manage.py" in cmd_str:
            return ("runserver", proc, cmd)
        elif "uwsgi" in cmd_str:
            return ("uwsgi", proc, cmd)

    return (None, None, None)

def get_python_path(cmd):
    return cmd[0]

def is_systemd(proc):
    try:
        with open(f"/proc/{proc.pid}/cgroup") as f:
            return "system.slice" in f.read()
    except:
        return False
