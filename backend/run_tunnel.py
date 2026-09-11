import subprocess
import time
import sys

def run_tunnel():
    cmd = ["npx", "-y", "localtunnel", "--port", "8000", "--subdomain", "acme-ride-agent"]
    while True:
        print("[Tunnel] Starting localtunnel on port 8000 (subdomain: acme-ride-agent)...", flush=True)
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                shell=True
            )
            for line in process.stdout:
                sys.stdout.write(line)
                sys.stdout.flush()
            process.wait()
            print(f"[Tunnel] Process exited with code {process.returncode}. Reconnecting in 3 seconds...", flush=True)
        except Exception as e:
            print(f"[Tunnel] Error running localtunnel: {e}. Retrying in 5 seconds...", flush=True)
        time.sleep(3)

if __name__ == "__main__":
    run_tunnel()
