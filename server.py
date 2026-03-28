#!/usr/bin/env python3
"""Sonar Viewer — lightweight dashboard server for sonar (port scanner).

Zero dependencies beyond Python stdlib.
Usage: python server.py [--port 7680]
"""

import argparse
import json
import os
import subprocess
import sys
from functools import partial
from http.server import HTTPServer, SimpleHTTPRequestHandler

SONAR_CMD = os.environ.get("SONAR_CMD", "sonar")


class SonarHandler(SimpleHTTPRequestHandler):
    """Serves static files from static/ and exposes two API endpoints."""

    def do_GET(self):
        if self.path == "/api/sonar":
            self._run_sonar("list", "--stats", "--json")
        elif self.path == "/api/next":
            self._run_sonar("next", "--json")
        elif self.path == "/":
            self.path = "/index.html"
            super().do_GET()
        else:
            super().do_GET()

    def _run_sonar(self, *args):
        cmd = [SONAR_CMD] + list(args)
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=15
            )
            if result.returncode != 0:
                self._json_error(
                    500,
                    f"sonar exited with code {result.returncode}: {result.stderr.strip()}",
                )
                return
            body = result.stdout.strip()
            # Validate JSON
            json.loads(body)
            self._json_response(200, body, raw=True)
        except FileNotFoundError:
            self._json_error(500, f"'{SONAR_CMD}' command not found on this system")
        except subprocess.TimeoutExpired:
            self._json_error(504, "sonar command timed out (15s)")
        except json.JSONDecodeError:
            # sonar returned non-JSON — pass it through anyway
            self._json_response(200, result.stdout.strip(), raw=True)
        except Exception as e:
            self._json_error(500, str(e))

    def _json_response(self, code, body, *, raw=False):
        payload = body.encode() if raw else json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _json_error(self, code, message):
        self._json_response(code, json.dumps({"error": message}), raw=True)

    def log_message(self, fmt, *args):
        # Cleaner log format
        sys.stderr.write(f"[sonar-viewer] {args[0]}\n")


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    static_dir = os.path.join(script_dir, "static")

    parser = argparse.ArgumentParser(description="Sonar Viewer dashboard server")
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("PORT", 7680)),
        help="Port to listen on (default: 7680, or $PORT)",
    )
    parser.add_argument(
        "--bind",
        default="0.0.0.0",
        help="Address to bind to (default: 0.0.0.0)",
    )
    args = parser.parse_args()

    handler = partial(SonarHandler, directory=static_dir)
    server = HTTPServer((args.bind, args.port), handler)

    print(f"[sonar-viewer] Serving on http://{args.bind}:{args.port}")
    print(f"[sonar-viewer] Static dir: {static_dir}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[sonar-viewer] Stopped.")
        server.server_close()


if __name__ == "__main__":
    main()
