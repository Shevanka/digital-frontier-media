# AI-Assisted Production System

## Purpose

A Python CLI that turns an editorial backlog item into a bilingual production package. It supports backlog listing, RSS trend discovery, AI-assisted research and drafting, storyboard generation, carousel copy, and platform-specific publication drafts.

## Workflow

1. **Backlog:** choose an evergreen idea or a dated trend lead.
2. **Discover:** collect recent publisher RSS and Google News RSS entries. Discovery output is a lead list, not evidence.
3. **Research:** create a canonical research brief with a thesis, source register, and claim register.
4. **Generate:** draft Indonesian and English scripts from the same research context.
5. **Storyboard:** create a shared visual sequence and on-screen text.
6. **Package:** create TikTok, Instagram Reels, and YouTube Shorts publication drafts in both languages, plus carousel copy and machine-readable JSON.
7. **Review:** a human verifies every factual claim and approves the package before publication.

## Requirements

- Python 3.10 or newer.
- Internet access for RSS discovery.
- An OpenAI-compatible API key for AI generation.
- No third-party Python dependencies are required by the core package.

## Setup

```bash
python --version
python -m venv .venv
# Windows PowerShell: .venv\\Scripts\\Activate.ps1
# macOS/Linux: source .venv/bin/activate
pip install -e .
cp production_engine/config/.env.example .env
```

Set `OPENAI_API_KEY` and optionally `OPENAI_BASE_URL`, `OPENAI_MODEL`, and `OPENAI_TIMEOUT_SECONDS` in `.env`. Never commit credentials.

## CLI

```bash
python -m production_engine.cli backlog
python -m production_engine.cli discover --days 7
python -m production_engine.cli produce --idea 01_ai-agents
python -m pytest -q
```

The `produce` command creates a dated folder under `content/production/`. Review the research brief first, then both language scripts, storyboard, and publication drafts.

## Editorial safeguards

- RSS summaries and headlines are discovery metadata, not proof.
- Sources must be opened and checked directly.
- Claims should be marked `VERIFIED`, `NEEDS_VERIFICATION`, or `CONTEXT_ONLY`.
- Remove or resolve claims needing verification before narration.
- Indonesian and English versions must preserve the same factual scope and caveats.
- AI-generated drafts are never automatically published.

## Scope and limitations

The system generates text-based production assets and metadata. It does not render finished video, synthesize voice, license footage, or publish to social platforms. Those remain separate production steps with human review.

## GitHub Actions

Workflows provide scheduled trend discovery, manual package generation, and automated tests. Secrets must be configured in repository settings before workflows that call the model API can generate content.
