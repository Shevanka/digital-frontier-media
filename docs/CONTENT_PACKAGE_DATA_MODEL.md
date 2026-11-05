# Content Package Data Model

Each generated package has a machine-readable `package.json` and human-readable Markdown files.

## Canonical fields

- `topic`: short topic name.
- `idea_id`: originating backlog identifier.
- `generated_at`: generation timestamp.
- `research_brief`: thesis, context, claim register, and source register.
- `scripts`: Indonesian and English short-video narration and carousel copy.
- `storyboard`: ordered scenes with timing, visual direction, overlays, narration references, and asset requirements.
- `platform_variants`: TikTok, Instagram Reels, and YouTube Shorts metadata for both languages.
- `review_status`: draft until human approval is explicitly recorded.

## Claim status

- `VERIFIED`: checked against an authoritative source and suitable for use within its stated scope.
- `NEEDS_VERIFICATION`: not ready for narration or publication.
- `CONTEXT_ONLY`: useful background or interpretation, not a standalone factual claim.

## Invariants

Both language versions must derive from the same approved research brief. Localization may change phrasing and examples but must not broaden claims, remove caveats, or invent evidence. A generated package remains a draft until editorial review is complete.
