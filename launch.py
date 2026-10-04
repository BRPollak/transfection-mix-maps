"""Launch the local app and open it once the server is ready."""
import argparse
import signal
import socket
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

from app_version import VERSION

parser = argparse.ArgumentParser()
parser.add_argument("--no-browser", action="store_true")
args = parser.parse_args()
app_dir = Path(__file__).resolve().parent
with socket.socket() as sock:
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
url = f"http://127.0.0.1:{port}"
process = subprocess.Popen([
    sys.executable, "-m", "streamlit", "run", str(app_dir / "app.py"),
    "--server.address", "127.0.0.1", "--server.port", str(port),
    "--server.headless", "true", "--browser.gatherUsageStats", "false",
], cwd=app_dir)


def request_shutdown(signum, frame):
    # The native Mac launcher sends SIGTERM when its window closes or it quits.
    # Route it through the same cleanup as Control-C so the server is not orphaned.
    raise KeyboardInterrupt


signal.signal(signal.SIGTERM, request_shutdown)
try:
    for _ in range(120):
        if process.poll() is not None:
            raise RuntimeError("The app server stopped during startup.")
        try:
            with urllib.request.urlopen(url + "/_stcore/health", timeout=1) as response:
                ready = response.status == 200
            if ready:
                break
        except (OSError, TimeoutError):
            time.sleep(0.25)
    else:
        raise RuntimeError("The app did not start within 30 seconds.")
    print(f"\nTransfection Mix Maps v{VERSION} is ready: {url}\nKeep this window open. Press Control-C to stop.\n", flush=True)
    if not args.no_browser:
        webbrowser.open(url)
    process.wait()
except KeyboardInterrupt:
    pass
finally:
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
