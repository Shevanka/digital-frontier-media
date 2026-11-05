import unittest

from production_engine.engine import enforce_source_policy

LEADS = [
    {
        "url": "https://cisa.example/a",
        "title": "Real title",
        "source": "CISA Alerts",
        "published_at": "2026-11-05T00:00:00+00:00",
        "source_trust": "primary_or_institutional",
    },
    {
        "url": "https://blog.example/b",
        "title": "Blog",
        "source": "Blog",
        "published_at": None,
        "source_trust": "secondary",
    },
    {
        "url": "https://news.google.com/rss/articles/x",
        "title": "Agg",
        "source": "Google News RSS",
        "published_at": None,
        "source_trust": "discovery_only",
    },
]


def package(sources, claims):
    return {"research_brief": {"sources": sources, "claims": claims}}


def claim(ids, status="VERIFIED", cid="c1"):
    return {"id": cid, "claim": "x", "status": status, "source_ids": ids}


class SourcePolicyTests(unittest.TestCase):
    def test_primary_lead_keeps_verified_and_metadata_comes_from_lead(self):
        data = package(
            [
                {
                    "id": "s1",
                    "url": "https://cisa.example/a",
                    "title": "Fake",
                    "publisher": "Forged",
                    "published_at": "1999",
                }
            ],
            [claim(["s1"])],
        )
        notes = enforce_source_policy(data, LEADS)
        src = data["research_brief"]["sources"][0]
        self.assertEqual(
            (src["title"], src["publisher"]), ("Real title", "CISA Alerts")
        )
        self.assertEqual(src["published_at"], "2026-11-05T00:00:00+00:00")
        self.assertEqual(data["research_brief"]["claims"][0]["status"], "VERIFIED")
        self.assertEqual(notes, [])

    def test_secondary_and_aggregator_leads_cannot_verify(self):
        for url in ("https://blog.example/b", "https://news.google.com/rss/articles/x"):
            data = package([{"id": "s1", "url": url}], [claim(["s1"])])
            enforce_source_policy(data, LEADS)
            self.assertEqual(
                data["research_brief"]["claims"][0]["status"], "NEEDS_VERIFICATION", url
            )

    def test_unknown_url_is_blanked_and_claim_downgraded(self):
        data = package([{"id": "s1", "url": "https://evil.example/"}], [claim(["s1"])])
        enforce_source_policy(data, LEADS)
        self.assertEqual(data["research_brief"]["sources"][0]["url"], "")
        self.assertEqual(
            data["research_brief"]["claims"][0]["status"], "NEEDS_VERIFICATION"
        )

    def test_one_weak_source_downgrades_claim(self):
        data = package(
            [
                {"id": "s1", "url": "https://cisa.example/a"},
                {"id": "s2", "url": "https://evil.example/"},
            ],
            [claim(["s1", "s2"])],
        )
        enforce_source_policy(data, LEADS)
        self.assertEqual(
            data["research_brief"]["claims"][0]["status"], "NEEDS_VERIFICATION"
        )

    def test_missing_or_unresolved_source_ids_downgrade(self):
        data = package(
            [{"id": "s1", "url": "https://cisa.example/a"}],
            [claim([], cid="a"), claim(["nope"], cid="b")],
        )
        enforce_source_policy(data, LEADS)
        self.assertEqual(
            [c["status"] for c in data["research_brief"]["claims"]],
            ["NEEDS_VERIFICATION"] * 2,
        )

    def test_non_verified_statuses_untouched_and_bad_shapes_tolerated(self):
        data = package(
            [{"id": "s1", "url": "https://evil.example/"}, "junk"],
            [claim(["s1"], "CONTEXT_ONLY"), "junk"],
        )
        enforce_source_policy(data, LEADS)
        self.assertEqual(data["research_brief"]["claims"][0]["status"], "CONTEXT_ONLY")
        self.assertEqual(enforce_source_policy({"research_brief": "x"}, LEADS), [])


if __name__ == "__main__":
    unittest.main()
