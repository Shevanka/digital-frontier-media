import io
import socket
import unittest
from unittest import mock

from production_engine import fetch, rss


def resolver(ip):
    family = socket.AF_INET6 if ":" in ip else socket.AF_INET
    return lambda *a, **k: [(family, socket.SOCK_STREAM, 6, "", (ip, 443))]


def patch_dns(ip):
    return mock.patch.object(fetch.socket, "getaddrinfo", resolver(ip))


class PublicUrlTests(unittest.TestCase):
    def test_public_address_allowed(self):
        with patch_dns("93.184.216.34"):
            fetch.assert_public_url("https://feed.example/rss")

    def test_non_public_addresses_rejected(self):
        for ip in (
            "127.0.0.1",
            "10.0.0.5",
            "192.168.1.1",
            "172.16.0.1",
            "169.254.169.254",
            "100.64.0.1",
            "0.0.0.0",
            "::1",
            "fe80::1",
            "fd00::1",
            "::ffff:127.0.0.1",
        ):
            with patch_dns(ip), self.assertRaises(fetch.UnsafeUrl, msg=ip):
                fetch.assert_public_url("https://feed.example/rss")

    def test_mixed_answers_rejected_if_any_is_private(self):
        mixed = lambda *a, **k: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443)),
        ]
        with (
            mock.patch.object(fetch.socket, "getaddrinfo", mixed),
            self.assertRaises(fetch.UnsafeUrl),
        ):
            fetch.assert_public_url("https://feed.example/rss")

    def test_bad_urls_rejected_without_dns(self):
        with mock.patch.object(
            fetch.socket, "getaddrinfo", side_effect=AssertionError("DNS used")
        ):
            for url in (
                "file:///etc/passwd",
                "ftp://a.example/x",
                "javascript:1",
                "https:///x",
                "https://u:p@a.example/",
                "https://a.example:notaport/",
            ):
                with self.assertRaises(fetch.UnsafeUrl, msg=url):
                    fetch.assert_public_url(url)

    def test_unresolvable_host_rejected(self):
        with (
            mock.patch.object(fetch.socket, "getaddrinfo", side_effect=socket.gaierror),
            self.assertRaises(fetch.UnsafeUrl),
        ):
            fetch.assert_public_url("https://nope.example/")


class RedirectTests(unittest.TestCase):
    def redirect(self, source, target):
        handler = fetch._CheckedRedirect()
        req = fetch.urllib.request.Request(source)
        return handler.redirect_request(req, io.BytesIO(), 302, "Found", {}, target)

    def test_redirect_to_internal_host_blocked(self):
        with patch_dns("169.254.169.254"), self.assertRaises(fetch.UnsafeUrl):
            self.redirect("https://feed.example/a", "https://metadata.internal/latest")

    def test_https_to_http_downgrade_blocked(self):
        with patch_dns("93.184.216.34"), self.assertRaises(fetch.UnsafeUrl):
            self.redirect("https://feed.example/a", "http://feed.example/a")

    def test_relative_and_public_redirect_followed(self):
        with patch_dns("93.184.216.34"):
            new = self.redirect("https://feed.example/a", "/b")
        self.assertEqual(new.full_url, "https://feed.example/b")

    def test_non_http_redirect_blocked(self):
        with patch_dns("93.184.216.34"), self.assertRaises(fetch.UnsafeUrl):
            self.redirect("https://feed.example/a", "file:///etc/passwd")


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FetchLimitedTests(unittest.TestCase):
    def fetch(self, body, **kw):
        with (
            patch_dns("93.184.216.34"),
            mock.patch.object(fetch._OPENER, "open", return_value=FakeResponse(body)),
        ):
            return fetch.fetch_limited("https://feed.example/rss", **kw)

    def test_returns_body_within_limit(self):
        self.assertEqual(self.fetch(b"x" * 100, max_bytes=100), b"x" * 100)

    def test_oversize_body_fails_instead_of_truncating(self):
        with self.assertRaises(ValueError):
            self.fetch(b"x" * 101, max_bytes=100)

    def test_deadline_is_enforced(self):
        ticks = iter([0.0, 0.0, 100.0, 100.0, 100.0])
        with (
            mock.patch.object(fetch.time, "monotonic", lambda: next(ticks)),
            self.assertRaises(TimeoutError),
        ):
            self.fetch(b"x" * 200_000, deadline=5)

    def test_private_start_url_never_opens_connection(self):
        opener = mock.Mock()
        with (
            patch_dns("127.0.0.1"),
            mock.patch.object(fetch._OPENER, "open", opener),
            self.assertRaises(fetch.UnsafeUrl),
        ):
            fetch.fetch_limited("https://feed.example/rss")
        opener.assert_not_called()

    def test_loopback_literal_rejected_for_real(self):
        with self.assertRaises(fetch.UnsafeUrl):
            fetch.fetch_limited("http://127.0.0.1:9/rss")


class DtdTests(unittest.TestCase):
    LAUGHS = (
        b'<?xml version="1.0"?><!DOCTYPE lolz [<!ENTITY lol "lol">'
        b'<!ENTITY lol2 "&lol;&lol;&lol;">]><rss><channel><item><title>&lol2;</title></item></channel></rss>'
    )

    def test_doctype_and_entity_rejected(self):
        for raw in (
            self.LAUGHS,
            b"<!doctype html><rss/>",
            b"<rss><!ENTITY x 'y'></rss>",
        ):
            with self.assertRaises(ValueError):
                fetch.reject_dtd(raw)

    def test_utf16_rejected_and_plain_feed_accepted(self):
        with self.assertRaises(ValueError):
            fetch.reject_dtd("<rss/>".encode("utf-16"))
        fetch.reject_dtd(b'<?xml version="1.0"?><rss><channel/></rss>')

    def test_fetch_feed_rejects_entity_bomb(self):
        with (
            mock.patch.object(rss, "fetch_limited", return_value=self.LAUGHS),
            self.assertRaises(ValueError),
        ):
            rss.fetch_feed("https://feed.example/rss", "Feed", "AI", "secondary")


if __name__ == "__main__":
    unittest.main()
