"""Local server: serves the report and lets its 'Update data' button re-run the pipeline.

Binds to 127.0.0.1 only. The update endpoint takes no parameters beyond which
sources to refresh, and rejects requests that do not come from the served page.
"""

from __future__ import annotations

import argparse
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class Job:
    def __init__(self):
        self.lock = threading.Lock()
        self.running = False
        self.log: list[str] = []
        self.error = ""
        self.runs = 0

    def state(self) -> dict:
        return {"running": self.running, "log": self.log[-12:], "error": self.error, "runs": self.runs}


def serve(args, run_update) -> int:
    job = Job()
    report = Path(args.report)
    if not report.exists():
        print(f"No report at {report} yet: run 'pssd-atlas update' once first.")
        return 1

    def worker(include_faers: bool):
        ns = argparse.Namespace(config=args.config, data=args.data, report=args.report, cache=args.cache, raw=args.raw,
                                no_cache=False, cache_days=0.0, skip=None)
        try:
            if include_faers:
                rc = run_update(ns, log=job.log.append)
            else:
                ns.skip = ["faers", "targets"]
                rc = run_update(ns, log=job.log.append)
            job.error = "Some sources could not be refreshed; their previous data was kept." if rc else ""
        except Exception as e:  # noqa: BLE001 - report any failure to the page
            job.error = f"Update failed: {e}"
        finally:
            job.runs += 1
            job.running = False

    class Handler(BaseHTTPRequestHandler):
        def _send(self, code: int, body: bytes, ctype: str) -> None:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, code: int, obj) -> None:
            self._send(code, json.dumps(obj).encode(), "application/json")

        def _local(self) -> bool:
            # Refuse DNS-rebinding and cross-site requests: the Host must be this server.
            host = (self.headers.get("Host") or "").split(":")[0]
            return host in ("127.0.0.1", "localhost")

        def do_GET(self):
            if not self._local():
                return self._json(403, {"error": "forbidden"})
            path = self.path.split("?")[0]
            if path in ("/", "/index.html"):
                return self._send(200, report.read_bytes(), "text/html; charset=utf-8")
            if path == "/api/status":
                return self._json(200, job.state())
            self._json(404, {"error": "not found"})

        def do_POST(self):
            # The custom header cannot be sent by a cross-site form or simple request.
            if not self._local() or self.headers.get("X-PSSD-Atlas") != "1":
                return self._json(403, {"error": "forbidden"})
            if self.path.split("?")[0] != "/api/update":
                return self._json(404, {"error": "not found"})
            length = min(int(self.headers.get("Content-Length") or 0), 1000)
            try:
                opts = json.loads(self.rfile.read(length) or b"{}")
            except ValueError:
                opts = {}
            with job.lock:
                if job.running:
                    return self._json(409, job.state())
                job.running, job.log, job.error = True, [], ""
            threading.Thread(target=worker, args=(bool(opts.get("faers")),), daemon=True).start()
            self._json(202, job.state())

        def log_message(self, *a):  # keep the terminal quiet
            pass

    httpd = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"PSSD Atlas running at http://127.0.0.1:{args.port}/  (Ctrl+C to stop)")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0
