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
from urllib.parse import urlparse, parse_qs

SONAR_CMD = os.environ.get("SONAR_CMD", "sonar")
CONFIG_PATH = None  # set in main()


def load_config():
    if CONFIG_PATH and os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"overrides": {}}


def save_config(data):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


class SonarHandler(SimpleHTTPRequestHandler):
    """Serves static files from static/ and exposes API endpoints."""

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/sonar":
            self._run_sonar("list", "--stats", "--json")
        elif parsed.path == "/api/next":
            params = parse_qs(parsed.query)
            args = ["next"]
            # sonar next [start_port] returns next available port after start_port
            if "from" in params:
                port_str = params["from"][0]
                if port_str.isdigit():
                    args.append(port_str)
            args.append("--json")
            self._run_sonar(*args)
        elif parsed.path == "/api/logs":
            params = parse_qs(parsed.query)
            container = params.get("container", [None])[0]
            if not container:
                self._json_error(400, "Missing 'container' parameter")
                return
            tail = params.get("tail", ["200"])[0]
            if not tail.isdigit():
                tail = "200"
            self._docker_logs(container, tail)
        elif parsed.path == "/api/config":
            config = load_config()
            self._json_response(200, json.dumps(config), raw=True)
        elif self.path == "/":
            self.path = "/index.html"
            super().do_GET()
        else:
            super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/config":
            try:
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length).decode("utf-8")
                data = json.loads(body)
                # Merge into existing config
                config = load_config()
                port_key = str(data.get("port", ""))
                if not port_key:
                    self._json_error(400, "Missing 'port' field")
                    return
                override = {}
                if "name" in data:
                    override["name"] = data["name"]
                if "description" in data:
                    override["description"] = data["description"]
                if "category" in data:
                    override["category"] = data["category"]
                if override:
                    config.setdefault("overrides", {})[port_key] = override
                else:
                    # Empty override = delete
                    config.get("overrides", {}).pop(port_key, None)
                save_config(config)
                self._json_response(200, json.dumps({"ok": True}), raw=True)
            except json.JSONDecodeError:
                self._json_error(400, "Invalid JSON")
            except Exception as e:
                self._json_error(500, str(e))
        else:
            self.send_error(404)

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

    def _docker_logs(self, container, tail):
        import re
        if not re.match(r'^[a-zA-Z0-9_.-]+$', container):
            self._json_error(400, "Invalid container name")
            return
        cmd = ["docker", "logs", "--tail", tail, container]
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=15
            )
            logs = result.stdout + result.stderr
            body = json.dumps({"container": container, "logs": logs})
            self._json_response(200, body, raw=True)
        except FileNotFoundError:
            self._json_error(500, "'docker' command not found")
        except subprocess.TimeoutExpired:
            self._json_error(504, "docker logs timed out (15s)")
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
    global CONFIG_PATH
    script_dir = os.path.dirname(os.path.abspath(__file__))
    static_dir = os.path.join(script_dir, "static")
    CONFIG_PATH = os.path.join(script_dir, "config.json")

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
