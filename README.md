# The Digital Frontier

**Understand Tomorrow, Today.**

The Digital Frontier is a bilingual editorial technology media project for Indonesian and global audiences. It covers artificial intelligence, technology and innovation, cybersecurity, tech news and internet culture, and the future of digital society.

## Editorial pillars

| Pillar | Initial allocation |
|---|---:|
| Artificial Intelligence | 30% |
| Technology & Innovation | 20% |
| Cybersecurity | 25% |
| Tech News & Internet Culture | 15% |
| Future & Digital Society | 10% |

## Production workflow

1. Select an evergreen topic from `content/ideas/` or discover a recent trend lead.
2. Research original sources and record claims, evidence, dates, and caveats.
3. Generate Indonesian and English drafts from one canonical factual brief.
4. Review scripts, storyboard, carousel copy, and platform-specific metadata.
5. Produce and edit the video, then complete the publishing checklist.
6. Publish manually after human approval and record performance.

## Quick start

Requires Python 3.10+.

```bash
python -m production_engine.cli backlog
python -m production_engine.cli discover --days 7
```

For AI-assisted package generation, copy `production_engine/config/.env.example` to `.env`, set `OPENAI_API_KEY`, and run:

```bash
python -m production_engine.cli produce --idea 01_ai-agents
```

The CLI uses an OpenAI-compatible Chat Completions endpoint. You can configure `OPENAI_BASE_URL`, `OPENAI_MODEL`, and `OPENAI_TIMEOUT_SECONDS`. Never commit API credentials.

## Repository guide

- `docs/`: brand, editorial, platform, and production-system documentation.
- `content/ideas/`: initial editorial backlog.
- `content/production/`: generated production packages.
- `production_engine/`: Python CLI, RSS discovery, and AI-assisted package generation.
- `research/`: fact-check policy, source notes, and trend snapshots.
- `templates/`: script, carousel, bilingual adaptation, and trend-report templates.
- `operations/`: production and publication checklists.
- `analytics/`: content tracker and weekly review resources.

## Editorial safeguards

RSS headlines and summaries are discovery leads, not evidence. Verify every material claim against original sources. Remove or resolve claims marked `NEEDS_VERIFICATION` before recording or publishing. Indonesian and English versions must preserve the same factual scope and caveats. AI-generated materials are drafts only; human editorial approval is mandatory. This repository does not automatically publish to social platforms.

## Current scope

The CLI creates text-based research briefs, scripts, storyboards, carousel copy, and publication metadata. It does not render finished video, synthesize voice, license assets, or publish content. Those remain human-controlled production steps.
