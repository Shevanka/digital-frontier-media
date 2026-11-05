import io
import unittest
from unittest import mock

from production_engine import rss
from production_engine.cli import main


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def fetch(xml: str):
    with mock.patch.object(
        rss.urllib.request, "urlopen", return_value=FakeResponse(xml.encode())
    ):
        return rss.fetch_feed("https://feed.example/rss", "Feed", "AI", "secondary")


def rss_item(title="T", link="https://a.example/x"):
    return f"<item><title>{title}</title><link>{link}</link></item>"


class UrlTests(unittest.TestCase):
    def test_only_plain_http_urls_are_accepted(self):
        for ok in ("https://a.example/x", "http://a.example/x?q=1"):
            self.assertEqual(rss.safe_url(ok), ok)
        for bad in (
            "javascript:alert(1)",
            "data:text/html,x",
            "file:///etc/passwd",
            "ftp://a.example/x",
            "//a.example/x",
            "https:///nohost",
            "https://u:p@a.example/",
            "https://a.example/a b",
            "https://a.example/x\ny",
            "",
            None,
            "https://a.example/" + "a" * 3000,
        ):
            self.assertIsNone(rss.safe_url(bad), repr(bad)[:60])

    def test_rss_items_with_unsafe_links_are_dropped(self):
        xml = (
            "<rss><channel>"
            + rss_item(link="javascript:alert(1)")
            + rss_item("Good")
            + "</channel></rss>"
        )
        items = fetch(xml)
        self.assertEqual([i["title"] for i in items], ["Good"])

    def test_atom_unsafe_link_dropped_and_title_capped(self):
        xml = (
            '<feed xmlns="http://www.w3.org/2005/Atom">'
            f'<entry><title>{"x" * 5000}</title><link href="https://a.example/1"/><updated>2026-11-05T01:00:00Z</updated></entry>'
            '<entry><title>Bad</title><link href="data:text/html,x"/></entry></feed>'
        )
        items = fetch(xml)
        self.assertEqual(len(items), 1)
        self.assertEqual(len(items[0]["title"]), rss.MAX_TITLE)


class DateTests(unittest.TestCase):
    def test_parse_iso_date(self):
        self.assertEqual(
            rss.parse_iso_date("2026-11-05T01:00:00Z"), "2026-11-05T01:00:00+00:00"
        )
        self.assertEqual(
            rss.parse_iso_date("2026-11-05T08:00:00+07:00"), "2026-11-05T01:00:00+00:00"
        )
        for bad in ("zzzz", "", None, "yesterday"):
            self.assertIsNone(rss.parse_iso_date(bad))

    def test_atom_garbage_date_is_not_kept_and_cannot_win_the_sort(self):
        xml = (
            '<feed xmlns="http://www.w3.org/2005/Atom">'
            '<entry><title>Spoof</title><link href="https://a.example/spoof"/><updated>zzzz</updated></entry>'
            '<entry><title>Real</title><link href="https://a.example/real"/><updated>2026-11-05T01:00:00Z</updated></entry>'
            "</feed>"
        )
        items = fetch(xml)
        self.assertIsNone(
            next(i for i in items if i["title"] == "Spoof")["published_at"]
        )
        ordered = sorted(items, key=rss._timestamp, reverse=True)
        self.assertEqual([i["title"] for i in ordered], ["Real", "Spoof"])


class TrendLimitTests(unittest.TestCase):
    def test_trend_limit_out_of_range_is_rejected(self):
        for value in ("0", "-1", "51"):
            with (
                self.assertRaises(SystemExit) as ctx,
                mock.patch("sys.stderr", new=io.StringIO()),
            ):
                main(["produce", "--idea", "x", "--trend-limit", value])
            self.assertEqual(ctx.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
