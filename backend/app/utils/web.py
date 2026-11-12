"""Safe remote job-posting fetching with SSRF protection."""
from __future__ import annotations

import ipaddress
import socket
from html.parser import HTMLParser
from urllib.parse import urlparse

import httpx

MAX_BYTES = 2_000_000


class UnsafeURLError(ValueError):
    pass


def _assert_public_host(host: str) -> None:
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as exc:
        raise UnsafeURLError(f"Could not resolve host: {host}") from exc
    for info in infos:
        address = info[4][0]
        try:
            ip = ipaddress.ip_address(address)
        except ValueError:
            continue
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            raise UnsafeURLError("URL points to a private or reserved address")


def validate_public_url(url: str) -> str:
    url = (url or "").strip()
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise UnsafeURLError("Only http(s) URLs are supported")
    if not parsed.hostname:
        raise UnsafeURLError("URL is missing a hostname")
    _assert_public_host(parsed.hostname)
    return url


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "noscript", "svg", "header", "footer", "nav"}:
            self.skip += 1
        if tag in {"p", "br", "li", "div", "h1", "h2", "h3", "h4", "tr"}:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in {"script", "style", "noscript", "svg", "header", "footer", "nav"} and self.skip:
            self.skip -= 1

    def handle_data(self, data):
        if not self.skip and data.strip():
            self.parts.append(data.strip() + " ")


def html_to_text(html: str) -> str:
    parser = _TextExtractor()
    parser.feed(html)
    text = "".join(parser.parts)
    lines = [line.strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)[:20000]


async def fetch_job_posting(url: str) -> str:
    validate_public_url(url)
    async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
        async with client.stream("GET", url, headers={"User-Agent": "RecruiMate/1.0"}) as response:
            if response.status_code >= 400:
                raise ValueError(f"Could not fetch the posting (HTTP {response.status_code})")
            content_type = response.headers.get("content-type", "")
            if "text" not in content_type and "html" not in content_type:
                raise ValueError("URL did not return a readable web page")
            chunks: list[bytes] = []
            total = 0
            async for chunk in response.aiter_bytes():
                total += len(chunk)
                if total > MAX_BYTES:
                    raise ValueError("Page is too large to analyse (2 MB limit)")
                chunks.append(chunk)
    raw = b"".join(chunks).decode("utf-8", errors="replace")
    text = html_to_text(raw)
    if len(text.strip()) < 120:
        raise ValueError("No readable job description was found at that URL")
    return text
