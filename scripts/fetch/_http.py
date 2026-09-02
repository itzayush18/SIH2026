"""Shared HTTP GET that survives Cloudflare/WAF TLS-fingerprint blocking.

Python's urllib/ssl has a bot-like TLS fingerprint (JA3) that Cloudflare-fronted
APIs (VesselAPI, Data Docked) reset after the first request — the symptom is a
repeated "Connection reset by peer" during the TLS handshake. curl presents a
browser-like TLS stack and gets through, so we use curl as the transport and
fall back to urllib only if curl is unavailable.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request

_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")


def _via_curl(url, headers):
    cmd = ["curl", "-s", "--fail-with-body", "--max-time", "45",
           "--compressed", "-A", _UA]
    for k, v in headers.items():
        cmd += ["-H", f"{k}: {v}"]
    cmd.append(url)
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"curl exit {p.returncode}: "
                           f"{(p.stderr or p.stdout)[:200]}")
    return json.loads(p.stdout)


def _via_urllib(url, headers):
    req = urllib.request.Request(url, headers={**headers, "User-Agent": _UA,
                                               "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=45) as r:
        return json.load(r)


def http_json(url, headers, tries=4, label="API"):
    """GET url -> parsed JSON, retrying on transient/WAF resets. Prefers curl."""
    use_curl = shutil.which("curl") is not None
    last = None
    for i in range(tries):
        try:
            return _via_curl(url, headers) if use_curl else _via_urllib(url, headers)
        except urllib.error.HTTPError as e:
            sys.exit(f"{label} HTTP {e.code}: {e.read().decode(errors='replace')[:300]}")
        except Exception as e:                       # curl failure, reset, timeout
            last = e
            if i < tries - 1:
                back = 1.5 * (i + 1)
                print(f"  {label} connection issue, retry {i+1}/{tries-1} in {back:.0f}s ...")
                time.sleep(back)
    sys.exit(f"{label} unreachable after {tries} tries: {last}")
