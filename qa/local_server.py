"""Serve this repo on 127.0.0.1 for as long as one script runs.

    from local_server import start
    BASE = start()        # "http://127.0.0.1:<port>/", serving this repo, gone when the script ends

Why: the checks used to need `python3 -m http.server 8462 &` running first. That server
dies whenever the cloud container restarts, and a leftover one can still answer on 8462
while serving another copy of the repo (seen 8 Oct 2026), so a check either failed for
nothing or quietly tested the wrong files. Now each script serves this repo itself, from
a background thread of its own process. There is nothing to start first and nothing to die.

    QA_PORT=8473   use that port for the script's own server (default: any free port)
    QA_BASE=<url>  use a server that is already running instead, e.g. the live site
"""
import functools
import http.server
import os
import sys
import threading
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class _Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


class _Server(http.server.ThreadingHTTPServer):
    def handle_error(self, request, client_address):
        # a page that moves on (a redirect) drops its half-sent files; that's not a problem worth a traceback
        if isinstance(sys.exc_info()[1], (BrokenPipeError, ConnectionResetError)):
            return
        super().handle_error(request, client_address)


def start():
    base = os.environ.get("QA_BASE")
    if base:
        base = base.rstrip("/") + "/"
        try:   # no proxy: the cloud proxy must never see a 127.0.0.1 address
            urllib.request.build_opener(urllib.request.ProxyHandler({})).open(base, timeout=5)
        except Exception as e:
            sys.exit(f"Nothing answers at QA_BASE={base} ({e}).\n"
                     "Leave QA_BASE unset and the script serves the repo itself.")
        return base
    port = int(os.environ.get("QA_PORT", "0"))
    try:
        server = _Server(("127.0.0.1", port), functools.partial(_Quiet, directory=ROOT))
    except OSError as e:
        sys.exit(f"Can't serve on port {port} ({e.strerror}). Leave QA_PORT unset to take any free port.")
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return f"http://127.0.0.1:{server.server_address[1]}/"


if __name__ == "__main__":   # by hand, to click around: python3 qa/local_server.py [port]
    os.environ.pop("QA_BASE", None)
    os.environ["QA_PORT"] = sys.argv[1] if len(sys.argv) > 1 else "8462"
    print("Serving this repo at", start(), "(Ctrl+C to stop)")
    threading.Event().wait()
