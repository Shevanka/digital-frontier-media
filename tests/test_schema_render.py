import copy
import json
import re
import tempfile
import unittest
from pathlib import Path

from production_engine import engine
from production_engine.safety import md_block, md_inline, md_url, redact


def good_package():
    def lang_block():
        return {
            "short_video": {"title": "T", "hook": "H", "narration": "N", "cta": "C"},
            "carousel": {
                "slides": [
                    {"headline": f"h{i}", "body": "b", "visual_direction": "v"}
                    for i in range(5)
                ]
            },
        }

    def variants():
        return {
            p: {"title": "t", "caption": "c", "hashtags": ["#ai", "#tech"]}
            for p in engine.PLATFORMS
        }

    return {
        "topic": "Topic",
        "research_brief": {
            "thesis": "x",
            "claims": [
                {
                    "id": "c1",
                    "claim": "x",
                    "status": "NEEDS_VERIFICATION",
                    "source_ids": ["s1"],
                    "caveat": "",
                }
            ],
            "sources": [
                {
                    "id": "s1",
                    "title": "T",
                    "url": "https://a.example/x",
                    "publisher": "P",
                }
            ],
            "open_questions": ["q"],
        },
        "languages": {"id": lang_block(), "en": lang_block()},
        "storyboard": [{"start": "00:00", "scene": "s", "visual": "v", "overlay": "o"}],
        "platform_variants": {"id": variants(), "en": variants()},
    }


class SchemaTests(unittest.TestCase):
    def test_good_package_passes(self):
        self.assertEqual(engine.validate_package(good_package()), [])

    def test_non_dict_and_wrong_types_never_raise(self):
        for bad in (None, [], "x", 5):
            self.assertTrue(engine.validate_package(bad))
        for path, value in (
            (("languages",), []),
            (("research_brief",), "x"),
            (("storyboard",), {"a": 1}),
            (("platform_variants", "id"), []),
            (("research_brief", "claims"), "nope"),
            (("research_brief", "claims"), ["str"]),
            (("research_brief", "sources"), [1]),
        ):
            data = good_package()
            node = data
            for key in path[:-1]:
                node = node[key]
            node[path[-1]] = value
            self.assertTrue(engine.validate_package(data), path)

    def test_limits_enums_ids_and_hashtags(self):
        cases = {
            "topic": lambda d: d.update(topic="x" * 201),
            "narration": lambda d: d["languages"]["id"]["short_video"].update(
                narration="x" * 3001
            ),
            "slides": lambda d: d["languages"]["en"]["carousel"].update(
                slides=d["languages"]["en"]["carousel"]["slides"] * 3
            ),
            "status": lambda d: d["research_brief"]["claims"][0].update(status="MAYBE"),
            "dup claim": lambda d: d["research_brief"]["claims"].append(
                dict(d["research_brief"]["claims"][0])
            ),
            "bad id": lambda d: d["research_brief"]["sources"][0].update(id="../x"),
            "hashtag": lambda d: d["platform_variants"]["id"]["tiktok"].update(
                hashtags=["#ok", "[x](javascript:1)"]
            ),
            "source_ids type": lambda d: d["research_brief"]["claims"][0].update(
                source_ids=[{"a": 1}]
            ),
        }
        for name, mutate in cases.items():
            data = good_package()
            mutate(data)
            self.assertTrue(engine.validate_package(data), name)

    def test_verified_without_known_source_still_rejected(self):
        data = good_package()
        data["research_brief"]["claims"][0].update(
            status="VERIFIED", source_ids=["nope"]
        )
        self.assertTrue(
            any(
                "Verified claim has no source" in e
                for e in engine.validate_package(data)
            )
        )

    def test_prune_drops_unknown_keys_languages_and_platforms(self):
        data = good_package()
        data["evil"] = 1
        data["languages"]["fr"] = {}
        data["platform_variants"]["id"]["../../x"] = {"caption": "c"}
        clean = engine.prune_package(data)
        self.assertNotIn("evil", clean)
        self.assertEqual(set(clean["languages"]), {"id", "en"})
        self.assertEqual(set(clean["platform_variants"]["id"]), set(engine.PLATFORMS))


class RenderTests(unittest.TestCase):
    def render(self, data):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        idea = root / "01_x.md"
        idea.write_text("idea", encoding="utf-8")
        return root, engine.render_package(root, idea, "idea", data)

    def test_hostile_platform_key_cannot_create_files(self):
        data = good_package()
        data["platform_variants"]["id"]["../../escape"] = {"caption": "c"}
        data["platform_variants"]["id"]["x:ads"] = {"caption": "c"}
        root, out = self.render(data)
        names = sorted(p.name for p in (out / "publication").iterdir())
        self.assertEqual(len(names), 6)
        self.assertFalse(any("escape" in n or "ads" in n for n in names))
        self.assertFalse((root / "escape.md").exists())

    def test_write_refuses_paths_outside_package(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "pkg"
            out.mkdir()
            with self.assertRaises(ValueError):
                engine._write(out, "../outside.md", "x")
            self.assertFalse((Path(tmp) / "outside.md").exists())

    def test_markdown_injection_is_neutralised_and_package_json_is_pruned(self):
        data = good_package()
        data["evil"] = "x"
        data["research_brief"]["sources"][0].update(
            title="[click](javascript:alert(1))", url="javascript:alert(1)"
        )
        data["research_brief"]["thesis"] = "<script>alert(1)</script>"
        data["languages"]["id"]["short_video"]["narration"] = (
            "<img src=x onerror=1> [a](javascript:1)"
        )
        _, out = self.render(data)
        brief = (out / "research_brief.md").read_text(encoding="utf-8")
        self.assertIsNone(re.search(r"(?<!\\)\]\(javascript:", brief))
        self.assertNotIn("<script>", brief)
        script = (out / "scripts" / "id.md").read_text(encoding="utf-8")
        self.assertNotIn("<img", script)
        self.assertIsNone(re.search(r"(?<!\\)\]\(", script))
        self.assertNotIn(
            "evil", json.loads((out / "package.json").read_text(encoding="utf-8"))
        )

    def test_valid_url_becomes_link_and_parentheses_are_encoded(self):
        data = good_package()
        data["research_brief"]["sources"][0]["url"] = "https://a.example/x_(1)"
        _, out = self.render(data)
        brief = (out / "research_brief.md").read_text(encoding="utf-8")
        self.assertIn("(https://a.example/x_%281%29)", brief)

    def test_storyboard_cell_cannot_break_table(self):
        data = good_package()
        data["storyboard"][0]["scene"] = "a | b\n| c"
        _, out = self.render(data)
        row = (out / "storyboard.md").read_text(encoding="utf-8").splitlines()[-1]
        self.assertEqual(row.replace("\\|", "").count("|"), 5)


class SafetyHelperTests(unittest.TestCase):
    def test_md_helpers(self):
        self.assertEqual(md_inline("a\nb *c*"), "a b \\*c\\*")
        self.assertNotIn("<", md_block("<b>x</b>"))
        self.assertEqual(md_url("javascript:alert(1)"), "")
        self.assertEqual(md_url("https://a.example/x)"), "https://a.example/x%29")

    def test_redact_removes_keys_and_bearer_tokens(self):
        import os
        from unittest import mock

        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "canary-secret-value-123"}):
            text = redact(
                "bad key canary-secret-value-123, Bearer abcdefghijkl, sk-abcdefghijkl"
            )
        self.assertNotIn("canary-secret-value-123", text)
        self.assertNotIn("abcdefghijkl", text)
        self.assertEqual(text.count("[REDACTED]"), 3)


if __name__ == "__main__":
    unittest.main()
