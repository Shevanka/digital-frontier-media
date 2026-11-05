import json
import os
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from unittest import mock

from production_engine import engine


class BaseUrlTests(unittest.TestCase):
    def test_default_is_accepted(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(engine.resolve_base_url(), engine.DEFAULT_BASE_URL)

    def test_rejects_non_https_and_odd_schemes(self):
        with mock.patch.dict(
            os.environ, {"ALLOW_CUSTOM_OPENAI_BASE_URL": "1"}, clear=True
        ):
            for url in (
                "http://api.openai.com/v1",
                "file:///etc/passwd",
                "ftp://api.openai.com",
                "api.openai.com",
            ):
                with self.assertRaises(ValueError, msg=url):
                    engine.resolve_base_url(url)

    def test_rejects_credentials_query_fragment(self):
        with mock.patch.dict(
            os.environ, {"ALLOW_CUSTOM_OPENAI_BASE_URL": "1"}, clear=True
        ):
            for url in (
                "https://u:p@api.openai.com/v1",
                "https://api.openai.com/v1?x=1",
                "https://api.openai.com/v1#f",
            ):
                with self.assertRaises(ValueError, msg=url):
                    engine.resolve_base_url(url)

    def test_untrusted_host_needs_opt_in(self):
        url = "https://gateway.example.com/v1"
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ValueError):
                engine.resolve_base_url(url)
        with mock.patch.dict(
            os.environ, {"ALLOW_CUSTOM_OPENAI_BASE_URL": "1"}, clear=True
        ):
            self.assertEqual(engine.resolve_base_url(url + "/"), url)

    def test_lookalike_host_rejected(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ValueError):
                engine.resolve_base_url("https://api.openai.com.evil.example/v1")


class SourceConfigTests(unittest.TestCase):
    def test_aggregator_feeds_are_never_primary_trust(self):
        from pathlib import Path
        from urllib.parse import urlsplit

        path = Path(engine.__file__).parent / "config" / "sources.json"
        for feed in json.loads(path.read_text(encoding="utf-8"))["feeds"]:
            if urlsplit(feed["url"]).hostname == "news.google.com":
                self.assertNotIn(
                    feed.get("trust"), engine.VERIFIABLE_TRUST, feed["name"]
                )


class RedirectTests(unittest.TestCase):
    def test_redirect_is_not_followed_and_key_not_forwarded(self):
        seen = []

        class Target(BaseHTTPRequestHandler):
            def do_GET(self):
                seen.append(self.headers.get("Authorization"))
                self.send_response(200)
                self.end_headers()

            do_POST = do_GET

            def log_message(self, *args):
                pass

        target = HTTPServer(("127.0.0.1", 0), Target)

        class Redirector(BaseHTTPRequestHandler):
            def do_POST(self):
                self.send_response(302)
                self.send_header(
                    "Location", f"http://127.0.0.1:{target.server_port}/steal"
                )
                self.end_headers()

            def log_message(self, *args):
                pass

        redirector = HTTPServer(("127.0.0.1", 0), Redirector)
        for srv in (target, redirector):
            threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            req = engine.urllib.request.Request(
                f"http://127.0.0.1:{redirector.server_port}/chat/completions",
                data=json.dumps({}).encode(),
                headers={"Authorization": "Bearer canary-not-a-real-key"},
                method="POST",
            )
            with self.assertRaises(engine.urllib.error.HTTPError) as ctx:
                engine._OPENER.open(req, timeout=5)
            ctx.exception.close()
            self.assertEqual(ctx.exception.code, 302)
            self.assertEqual(seen, [])
        finally:
            for srv in (target, redirector):
                srv.shutdown()
                srv.server_close()


if __name__ == "__main__":
    unittest.main()
