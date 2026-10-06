import subprocess
import signal
import os
import time


def find_django_path(cmd):
    """
    Try to locate directory containing manage.py
    """
    for arg in cmd:
        if "manage.py" in arg:
            abs_path = os.path.abspath(arg)
            return os.path.dirname(abs_path)

    # fallback: search in current dir
    if os.path.exists("manage.py"):
        return os.getcwd()

    return None


def get_safe_cwd(proc, cmd):
    """
    Get reliable working directory
    """
    # 🔹 Try from process
    try:
        cwd = proc.cwd()
        if cwd and os.path.exists(cwd):
            return cwd
    except:
        pass

    # 🔹 Try from command
    cmd_path = find_django_path(cmd)
    if cmd_path:
        return cmd_path

    # 🔹 Final fallback
    return os.getcwd()


def restart_process(proc, cmd, env):
    print(f"\n🔁 Restarting process PID={proc.pid}")

    # 🔹 Step 1: Resolve working directory safely
    cwd = get_safe_cwd(proc, cmd)
    print(f"📁 Using Working Dir: {cwd}")

    # 🔹 Step 2: Stop existing process safely
    try:
        proc.send_signal(signal.SIGTERM)

        try:
            proc.wait(timeout=10)
            print("✅ Process terminated gracefully")
        except subprocess.TimeoutExpired:
            print("⚠️ Graceful stop failed, killing process")
            proc.kill()

    except Exception as e:
        print(f"❌ Error stopping process: {e}")
        try:
            proc.kill()
        except:
            pass

    # 🔹 Step 3: Build new command
    new_cmd = ["opentelemetry-instrument"] + cmd

    print(f"🚀 Starting: {new_cmd}")

    # 🔹 Step 4: Start process with logs (IMPORTANT)
    try:
        new_proc = subprocess.Popen(
            new_cmd,
            env=env,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        # 🔹 Step 5: Validate startup (VERY IMPORTANT)
        time.sleep(3)

        if new_proc.poll() is not None:
            stdout, stderr = new_proc.communicate()
            print("❌ Process failed to start!")
            print("STDOUT:", stdout.decode())
            print("STDERR:", stderr.decode())
            return False

        print("✅ Process restarted successfully with OpenTelemetry")
        return True

    except Exception as e:
        print(f"❌ Failed to start process: {e}")
        return False