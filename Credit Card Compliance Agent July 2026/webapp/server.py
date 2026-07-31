#!/usr/bin/env python3
"""
ComplyLine Local Server
=======================
Runs a local server that:
  1. Serves ComplyLine_v4.html at http://localhost:8080
  2. Proxies /api/claude → api.anthropic.com (fixes CORS)
  3. Opens your browser automatically

Usage:
  python3 server.py
  python3 server.py --port 8080
  python3 server.py --key sk-ant-your-key-here
"""

import http.server
import urllib.request
import urllib.error
import json
import os
import sys
import argparse
import webbrowser
import threading
import time
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────
DEFAULT_PORT = 8080
ANTHROPIC_API = "https://api.anthropic.com"
DIR = Path(__file__).parent

# ── CORS headers added to every response ──────────────────────────────────────
CORS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, x-api-key, anthropic-version, anthropic-dangerous-direct-browser-access",
}


class Handler(http.server.SimpleHTTPRequestHandler):

    def __init__(self, *args, api_key=None, **kwargs):
        self.api_key = api_key
        # Serve files from the same directory as server.py
        super().__init__(*args, directory=str(DIR), **kwargs)

    def log_message(self, fmt, *args):
        # Clean up log output
        msg = fmt % args
        if "200" in msg:
            print(f"  ✓ {self.path}")
        elif "404" in msg:
            print(f"  ✗ 404: {self.path}")
        elif "/api/" in self.path:
            print(f"  → {msg.strip()}")

    def send_cors(self):
        for k, v in CORS.items():
            self.send_header(k, v)

    # ── Handle OPTIONS preflight ──────────────────────────────────────────────
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_cors()
        self.end_headers()

    # ── Proxy POST /api/claude → api.anthropic.com/v1/messages ───────────────
    def do_POST(self):
        if self.path == "/api/claude":
            self._proxy_claude()
        else:
            self.send_error(404, "Not found")

    def _proxy_claude(self):
        try:
            # Read request body
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)

            # Get API key: prefer request header, fall back to server arg, then env
            api_key = (
                self.headers.get("x-api-key")
                or self.api_key
                or os.environ.get("ANTHROPIC_API_KEY", "")
            )
            if not api_key:
                self._json_error(400, "No API key. Set ANTHROPIC_API_KEY env var or pass --key")
                return

            # Forward to Anthropic
            req = urllib.request.Request(
                f"{ANTHROPIC_API}/v1/messages",
                data=body,
                headers={
                    "Content-Type": "application/json",
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = resp.read()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_cors()
                self.end_headers()
                self.wfile.write(data)
                print(f"  ✓ Claude API → {len(data)} bytes")

        except urllib.error.HTTPError as e:
            error_body = e.read()
            self.send_response(e.code)
            self.send_header("Content-Type", "application/json")
            self.send_cors()
            self.end_headers()
            self.wfile.write(error_body)
            print(f"  ✗ Claude API error {e.code}: {error_body[:200]}")
        except Exception as e:
            self._json_error(500, str(e))
            print(f"  ✗ Proxy error: {e}")

    def _json_error(self, code, msg):
        body = json.dumps({"error": {"type": "proxy_error", "message": msg}}).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_cors()
        self.end_headers()
        self.wfile.write(body)


def make_handler(api_key):
    """Factory to inject api_key into handler."""
    def handler(*args, **kwargs):
        Handler(*args, api_key=api_key, **kwargs)
    return handler


def patch_html(port):
    """
    Patch the HTML file so it calls /api/claude (local proxy)
    instead of https://api.anthropic.com/v1/messages directly.
    Creates ComplyLine_v4_local.html — leaves original untouched.
    """
    src = DIR / "ComplyLine_v4.html"
    dst = DIR / "ComplyLine_v4_local.html"

    if not src.exists():
        print(f"\n  ⚠  ComplyLine_v4.html not found in {DIR}")
        print(f"     Download it and put it in the same folder as server.py\n")
        return False

    html = src.read_text(encoding="utf-8")

    # Replace the fetch URL
    old = "https://api.anthropic.com/v1/messages"
    new = f"http://localhost:{port}/api/claude"
    if old not in html:
        print("  ⚠  Could not find API URL in HTML — file may already be patched or different version.")
        # Try to use as-is
        dst.write_text(html, encoding="utf-8")
        return True

    patched = html.replace(old, new)

    # Also remove the x-api-key header from fetch (server handles it)
    # This is optional — server accepts it from the request too
    dst.write_text(patched, encoding="utf-8")
    print(f"  ✓ Created {dst.name} (API calls proxied through local server)")
    return True


def main():
    parser = argparse.ArgumentParser(description="ComplyLine Local Server")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--key", type=str, default="", help="Anthropic API key (optional — can also set in the app)")
    parser.add_argument("--no-open", action="store_true", help="Don't auto-open browser")
    args = parser.parse_args()

    port = args.port
    api_key = args.key or os.environ.get("ANTHROPIC_API_KEY", "")

    print("\n" + "═" * 55)
    print("  ⚖  ComplyLine — Credit Card Compliance Platform")
    print("═" * 55)

    # Patch HTML file
    ok = patch_html(port)
    if not ok:
        sys.exit(1)

    # Start server
    handler = make_handler(api_key)
    server = http.server.HTTPServer(("localhost", port), handler)

    url = f"http://localhost:{port}/ComplyLine_v4_local.html"
    print(f"\n  🌐  Server running at: {url}")
    if api_key:
        print(f"  🔑  API key: {api_key[:12]}…{api_key[-4:]} (loaded from {'--key' if args.key else 'environment'})")
    else:
        print(f"  🔑  No API key set — enter it in Settings inside the app")
    print(f"\n  Press Ctrl+C to stop\n")

    # Open browser after short delay
    if not args.no_open:
        def open_browser():
            time.sleep(1.2)
            webbrowser.open(url)
        threading.Thread(target=open_browser, daemon=True).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n\n  Server stopped. Goodbye!\n")


if __name__ == "__main__":
    main()
