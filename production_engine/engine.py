from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


def read_idea(root: Path, identifier: str) -> tuple[Path, str]:
    candidates = [p for p in (root / "content" / "ideas").glob("*.md") if p.name != "30_CONTENT_IDEAS.md"]
    matches = [p for p in candidates if p.stem == identifier or p.stem.endswith(identifier) or identifier in p.stem]
    if not matches:
        raise FileNotFoundError(f"No idea matched '{identifier}'. Run the backlog command.")
    if len(matches) > 1:
        raise ValueError("Ambiguous idea identifier: " + ", ".join(p.stem for p in matches))
    return matches[0], matches[0].read_text(encoding="utf-8")


def latest_trends(root: Path, limit: int = 12) -> list[dict]:
    files = sorted((root / "research" / "trends").glob("*.json"), reverse=True)
    if not files:
        return []
    return json.loads(files[0].read_text(encoding="utf-8")).get("items", [])[:limit]


def build_prompt(idea: str, trends: list[dict], brand: str, policy: str) -> str:
    return f'''You are an editorial researcher and bilingual technology video producer. Return valid JSON only.

BRAND GUIDE:\n{brand}\n\nFACT-CHECK POLICY:\n{policy}\n\nBACKLOG IDEA:\n{idea}\n\nTREND LEADS (discovery only, not proof):\n{json.dumps(trends, ensure_ascii=False)}\n
Create a package with this exact structure: topic, pillar, editorial_angle, audience_value, research_brief (thesis, claims, sources, open_questions, editorial_disclaimer), languages (id and en; each has short_video and carousel with at least 5 slides), storyboard (array), platform_variants (id and en; each has tiktok, instagram_reels, youtube_shorts with title, caption, hashtags), derivative_ideas, production_notes. Each claim has id, claim, status (VERIFIED, NEEDS_VERIFICATION, CONTEXT_ONLY), source_ids, caveat. Each source has id, title, url, publisher, published_at, source_type, what_it_supports. Use only exact URLs from trend leads; otherwise leave URL blank and mark source suggested/unverified. Default claims to NEEDS_VERIFICATION. Never invent facts, URLs, dates, quotes, statistics, or product capabilities. Keep both languages factually equivalent. Write 30–45 second scripts, 5–8 slide carousels, and a shot-by-shot vertical storyboard. Output JSON only, no markdown fences.'''


def call_llm(prompt: str) -> dict:
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if not key:
        raise RuntimeError("OPENAI_API_KEY is missing. Configure it in .env.")
    base = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    timeout = int(os.getenv("OPENAI_TIMEOUT_SECONDS", "120"))
    payload = {"model": model, "messages": [{"role": "system", "content": "Return only valid JSON."}, {"role": "user", "content": prompt}], "response_format": {"type": "json_object"}}
    req = urllib.request.Request(base + "/chat/completions", data=json.dumps(payload).encode(), headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            body = json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")[:1000]
        raise RuntimeError(f"Model API returned HTTP {exc.code}: {detail}") from exc
    content = body["choices"][0]["message"]["content"]
    return json.loads(content)


def validate_package(data: dict) -> list[str]:
    errors = []
    for key in ("topic", "research_brief", "languages", "storyboard", "platform_variants"):
        if key not in data:
            errors.append(f"Missing top-level field: {key}")
    for lang in ("id", "en"):
        language = data.get("languages", {}).get(lang, {})
        if not language.get("short_video", {}).get("narration"):
            errors.append(f"Missing {lang} narration")
        if len(language.get("carousel", {}).get("slides", [])) < 5:
            errors.append(f"{lang} carousel needs at least 5 slides")
        for platform in ("tiktok", "instagram_reels", "youtube_shorts"):
            if not data.get("platform_variants", {}).get(lang, {}).get(platform, {}).get("caption"):
                errors.append(f"Missing caption: {lang}/{platform}")
    if not data.get("storyboard"):
        errors.append("Storyboard is empty")
    allowed = {"VERIFIED", "NEEDS_VERIFICATION", "CONTEXT_ONLY"}
    source_ids = {s.get("id") for s in data.get("research_brief", {}).get("sources", [])}
    for claim in data.get("research_brief", {}).get("claims", []):
        if claim.get("status") not in allowed:
            errors.append(f"Invalid claim status: {claim.get('id')}")
        if claim.get("status") == "VERIFIED" and not set(claim.get("source_ids", [])).intersection(source_ids):
            errors.append(f"Verified claim has no source: {claim.get('id')}")
    return errors


def render_package(root: Path, idea_path: Path, idea_text: str, data: dict) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    out = root / "content" / "production" / f"{stamp}-{idea_path.stem}"
    out.mkdir(parents=True, exist_ok=False)
    (out / "package.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "source_backlog_idea.md").write_text(idea_text, encoding="utf-8")
    brief = data.get("research_brief", {})
    lines = [f"# Research brief: {data.get('topic','')}", "", f"**Thesis:** {brief.get('thesis','')}", "", "## Claims", ""]
    for claim in brief.get("claims", []):
        lines.append(f"- **{claim.get('status')}** {claim.get('claim')} (sources: {', '.join(claim.get('source_ids', []))}; caveat: {claim.get('caveat','')})")
    lines += ["", "## Sources", ""]
    for source in brief.get("sources", []):
        lines.append(f"- [{source.get('title', source.get('id','Source'))}]({source.get('url','')}) · {source.get('publisher','')} · {source.get('published_at','')} · {source.get('what_it_supports','')}")
    lines += ["", "## Open questions", ""] + [f"- {x}" for x in brief.get("open_questions", [])]
    (out / "research_brief.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    scripts = out / "scripts"; scripts.mkdir()
    for lang in ("id", "en"):
        obj = data.get("languages", {}).get(lang, {})
        video = obj.get("short_video", {}); carousel = obj.get("carousel", {})
        text = [f"# {data.get('topic','')} · {lang.upper()}", "", "**DRAFT: human review required**", "", f"## {video.get('title','')}", "", f"**Hook:** {video.get('hook','')}", "", video.get("narration", ""), "", f"**CTA:** {video.get('cta','')}", "", "## Carousel", ""]
        for i, slide in enumerate(carousel.get("slides", []), 1):
            text += [f"### {i}. {slide.get('headline','')}", slide.get("body", ""), f"Visual: {slide.get('visual_direction','')}", ""]
        (scripts / f"{lang}.md").write_text("\n".join(text), encoding="utf-8")
    story = ["# Storyboard", "", "| Time | Scene | Visual | Overlay |", "|---|---|---|---|"]
    for scene in data.get("storyboard", []):
        story.append("| " + " | ".join(str(scene.get(k, "")).replace("|", "\\|").replace("\n", " ") for k in ("start", "scene", "visual", "overlay")) + " |")
    (out / "storyboard.md").write_text("\n".join(story) + "\n", encoding="utf-8")
    pub = out / "publication"; pub.mkdir()
    for lang in ("id", "en"):
        for platform, details in data.get("platform_variants", {}).get(lang, {}).items():
            content = f"# {platform} · {lang.upper()}\n\n**DRAFT — do not publish before editorial approval**\n\n## Title\n{details.get('title','')}\n\n## Caption\n{details.get('caption','')}\n\n## Hashtags\n{' '.join(details.get('hashtags', []))}\n\n- [ ] Claims verified\n- [ ] Assets licensed\n- [ ] Human approval recorded\n"
            (pub / f"{lang}-{platform}.md").write_text(content, encoding="utf-8")
    (out / "README.md").write_text("# Production package\n\nGenerated draft. Verify every claim against original sources, confirm bilingual parity and asset rights, and record human approval before publication.\n", encoding="utf-8")
    return out
