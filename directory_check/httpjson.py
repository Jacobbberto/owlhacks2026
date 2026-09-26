"""Tiny JSON-over-HTTP helper built on the standard library (no dependencies)."""

import json
import os
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request

USER_AGENT = "owlhacks2026-directory-check/0.1"


def _ssl_context():
    # python.org builds on macOS ship without CA certs unless "Install Certificates"
    # was run, so fall back to certifi or the system bundle when needed.
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        pass
    paths = ssl.get_default_verify_paths()
    if not (paths.cafile and os.path.exists(paths.cafile)) and os.path.exists("/etc/ssl/cert.pem"):
        return ssl.create_default_context(cafile="/etc/ssl/cert.pem")
    return ssl.create_default_context()


_SSL_CONTEXT = _ssl_context()


class APIError(Exception):
    def __init__(self, message, status=None, body=None):
        super().__init__(message)
        self.status = status
        self.body = body


def get_json(url, params=None, headers=None, timeout=15, retries=2, backoff=1.0):
    """GET `url` with query `params` and return the decoded JSON body.

    Retries on network errors, 429 and 5xx responses with exponential backoff.
    `params` may be a dict or a list of (key, value) pairs (for repeated keys
    such as FHIR's `_include`).
    """
    if params:
        url = f"{url}{'&' if '?' in url else '?'}{urllib.parse.urlencode(params, doseq=True)}"
    req_headers = {"Accept": "application/json", "User-Agent": USER_AGENT}
    req_headers.update(headers or {})

    for attempt in range(retries + 1):
        request = urllib.request.Request(url, headers=req_headers)
        try:
            with urllib.request.urlopen(request, timeout=timeout, context=_SSL_CONTEXT) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            if (e.code == 429 or e.code >= 500) and attempt < retries:
                time.sleep(backoff * 2**attempt)
                continue
            raise APIError(f"HTTP {e.code} for {url}", status=e.code, body=body) from e
        except (urllib.error.URLError, TimeoutError) as e:
            if attempt < retries:
                time.sleep(backoff * 2**attempt)
                continue
            raise APIError(f"Request failed for {url}: {e}") from e
        except json.JSONDecodeError as e:
            raise APIError(f"Non-JSON response from {url}") from e
