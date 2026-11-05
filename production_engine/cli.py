from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path
from . import __version__
from .engine import build_prompt, call_llm, latest_trends, read_idea, render_package, validate_package
from .rss import discover

ROOT = Path(__file__).resolve().parents[1]

def load_dotenv() -> None:
    path = ROOT / ".env"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip("\"'"))

def backlog() -> int:
    ideas = sorted(p for p in (ROOT / "content" / "ideas").glob("*.md") if p.name != "30_CONTENT_IDEAS.md")
    print(f"Backlog ideas: {len(ideas)}")
    for path in ideas:
        title = next((line[2:].strip() for line in path.read_text(encoding="utf-8").splitlines() if line.startswith("# ")), path.stem)
        print(f"- {path.stem}: {title}")
    return 0

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="digital-frontier", description="AI-assisted bilingual content production")
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("backlog", help="List editorial backlog")
    trend = sub.add_parser("discover", help="Discover RSS trend leads")
    trend.add_argument("--days", type=int, default=7)
    trend.add_argument("--root", type=Path, default=ROOT)
    produce = sub.add_parser("produce", help="Generate a bilingual package")
    produce.add_argument("--idea", required=True)
    produce.add_argument("--trend-limit", type=int, default=12)
    produce.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    if args.command == "backlog":
        return backlog()
    if args.command == "discover":
        if not 1 <= args.days <= 90:
            parser.error("--days must be between 1 and 90")
        result = discover(args.root, args.days)
        print(f"Saved {len(result['items'])} trend leads; feed errors: {len(result['errors'])}")
        return 0
    if args.command == "produce":
        load_dotenv()
        try:
            idea_path, idea_text = read_idea(args.root, args.idea)
            trends = latest_trends(args.root, args.trend_limit)
            brand = (args.root / "docs" / "BRAND_GUIDE.md").read_text(encoding="utf-8")
            policy = (args.root / "research" / "RESEARCH_AND_FACT_CHECK_POLICY.md").read_text(encoding="utf-8")
            data = call_llm(build_prompt(idea_text, trends, brand, policy))
            errors = validate_package(data)
            if errors:
                print("\n".join(errors), file=sys.stderr)
                return 2
            known_urls = {item.get("url") for item in trends}
            for source in data.get("research_brief", {}).get("sources", []):
                if source.get("url") not in known_urls:
                    source["url"] = ""
                    source["source_type"] = "suggested_source_not_yet_verified"
                    for claim in data.get("research_brief", {}).get("claims", []):
                        if source.get("id") in claim.get("source_ids", []):
                            claim["status"] = "NEEDS_VERIFICATION"
            out = render_package(args.root, idea_path, idea_text, data)
            print(f"Package created: {out.relative_to(args.root)}")
            print("DRAFT only. Human fact-check and approval are mandatory.")
            return 0
        except Exception as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1
    return 1

if __name__ == "__main__":
    raise SystemExit(main())
