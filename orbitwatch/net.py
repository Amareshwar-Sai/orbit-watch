"""Bounded HTTPS retrieval. No proxies, redirects, cookies, or arbitrary ports."""

import http.client
import ipaddress
import socket
import ssl
import time
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

MAX_BYTES = 1_048_576


def canonical_url(value):
    if not isinstance(value, str) or len(value) > 4096:
        raise ValueError("URL must be a string of at most 4096 characters")
    if any(ord(c) < 33 for c in value) or "\\" in value:
        raise ValueError("URL contains whitespace or forbidden characters")
    p = urlsplit(value)
    if p.scheme != "https" or not p.hostname or p.username or p.password:
        raise ValueError("Only HTTPS URLs without credentials are accepted")
    if p.port not in (None, 443):
        raise ValueError("Only HTTPS port 443 is accepted")
    host = p.hostname.encode("idna").decode("ascii").lower()
    if host.endswith(".") or ":" in host:
        raise ValueError("Use a normal DNS hostname")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise ValueError("IP-literal URLs are not accepted")
    if "." not in host or host.endswith((".localhost", ".local", ".internal")):
        raise ValueError("Local hostnames are not accepted")
    query = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True)
             if not k.lower().startswith("utm_") and k.lower() not in ("fbclid", "gclid")]
    return urlunsplit(("https", host, p.path or "/", urlencode(query), ""))


def public_addresses(host):
    addresses = sorted({a[4][0] for a in socket.getaddrinfo(
        host, 443, type=socket.SOCK_STREAM)})
    if not addresses or any(not ipaddress.ip_address(a).is_global for a in addresses):
        raise ValueError("DNS resolved to a non-public address; fetch blocked")
    return addresses


class PinnedHTTPS(http.client.HTTPSConnection):
    """Connect to the validated numeric address; TLS still checks original host."""

    def __init__(self, host, address):
        super().__init__(host, timeout=10, context=ssl.create_default_context())
        self.address = address

    def connect(self):
        raw = socket.create_connection((self.address, 443), timeout=self.timeout)
        try:
            self.sock = self._context.wrap_socket(raw, server_hostname=self.host)
        except Exception:
            raw.close()
            raise


def read_bounded(response, limit=MAX_BYTES):
    size = response.getheader("Content-Length")
    if size and int(size) > limit:
        raise ValueError("Source exceeds the 1 MiB limit")
    if response.getheader("Content-Encoding", "identity").lower() != "identity":
        raise ValueError("Compressed responses are not supported")
    chunks, total = [], 0
    deadline = time.monotonic() + 30
    while True:
        if time.monotonic() > deadline:
            raise TimeoutError("Source read deadline exceeded")
        chunk = response.read1(min(16384, limit + 1 - total))
        if not chunk:
            break
        chunks.append(chunk)
        total += len(chunk)
        if total > limit:
            raise ValueError("Source exceeds the 1 MiB limit")
    return b"".join(chunks)


def fetch(url, allowed_hosts):
    url = canonical_url(url)
    p = urlsplit(url)
    if p.hostname not in allowed_hosts:
        raise ValueError("Host is not explicitly allowlisted in sources.json")
    address = public_addresses(p.hostname)[0]
    conn = PinnedHTTPS(p.hostname, address)
    try:
        conn.request("GET", p.path + ("?" + p.query if p.query else ""), headers={
            "User-Agent": "OrbitWatch/0.1 (personal research; bounded RSS reader)",
            "Accept-Encoding": "identity", "Accept": "application/xml,text/xml,text/html,*/*;q=0.1",
        })
        response = conn.getresponse()
        if response.status != 200:
            raise ValueError(f"HTTP {response.status}; redirects are intentionally not followed")
        return read_bounded(response)
    finally:
        conn.close()
