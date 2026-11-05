# Security Audit: Digital Frontier Media

| Item             | Value                                                                           |
| ---------------- | ------------------------------------------------------------------------------- |
| Repository       | `digital-frontier-media` (`origin`: github.com/Shevanka/digital-frontier-media) |
| Audited revision | `main` @ `00ab161` (merge of PR #1) plus the working tree at audit time         |
| Audit date       | 2026-11-05                                                                      |
| Type             | Static review of code, configuration and Git history. No dynamic testing.       |
| Auditor role     | Senior Python application security engineer                                     |

> **CVSS note.** CVSS 4.0 vectors below are _estimates_ made by hand and not run through the official FIRST calculator. Treat the numeric bands (Low / Medium / High) as the signal, not the exact score. This is a small CLI, not an internet-facing service, so many standard vectors (AV:N) do not apply.

---

## Remediation status (updated after the audit)

The findings in sections 1 and 3 describe the state at audit time (`00ab161`) and are left unchanged. P0/P1 remediation was merged in PR #3. P2 remediation is on branch `security/p2-hardening`. Verified with 64 unit tests (`python -m unittest discover -s tests`). No live model or feed calls were made, so model behaviour under injection is still untested.

| Finding    | Status       | What changed                                                                                                                                                                                                                                                                                                | Remaining                                                                                                                                                   |
| ---------- | ------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- |
| F-01       | Fixed        | `engine.resolve_base_url()` accepts only `https` URLs without credentials, query or fragment. Hosts other than `api.openai.com` need `ALLOW_CUSTOM_OPENAI_BASE_URL=1`. The model call uses an opener that never follows redirects. A local redirect test shows the `Authorization` header is not forwarded. | none for the model call                                                                                                                                     |
| F-02       | Mitigated    | Feed leads are sent in a separate message inside per-call random boundary markers. The system message says they are untrusted data. Leads are reduced to 8 known fields, control characters stripped and lengths capped.                                                                                    | Mitigation only: the model can still be influenced. Real protection is F-03 plus human review. Not tested against a real model.                             |
| F-03       | Fixed        | `engine.enforce_source_policy()`: a claim stays `VERIFIED` only if every cited source is a trend lead with `primary` or `primary_or_institutional` trust. Source title, publisher, date and URL are taken from the lead, not the model.                                                                     | The model can still emit `VERIFIED`. The audit recommended setting it only after human review.                                                              |
| F-04 | Mostly fixed | Title capped at 300 chars and URL at 2048; Atom dates parsed and normalised, invalid dates dropped; sort uses parsed timestamps; `--trend-limit` limited to 1-50; leads are sanitised before they reach the prompt. | Undated items are still kept (sorted last); trend-file freshness is not checked. |
| F-05, F-06 | Fixed (see limitation) | `fetch.py`: feed URLs and every redirect hop must be http(s) and resolve only to public addresses, https cannot be downgraded, at most 3 redirects, oversize bodies fail instead of being truncated, a wall-clock deadline applies, and XML with DOCTYPE/ENTITY (or UTF-16) is rejected before parsing. | DNS rebinding is not covered (name is resolved once to check and again to connect). The deadline is checked between reads, so the worst case is about deadline + socket timeout. |
| F-07 | Fixed | Links must be plain `http`/`https` at ingest, and generated Markdown (research brief, scripts, storyboard, publication files, trend report) escapes titles, captions, claims and sources; link targets are validated and parentheses encoded; HTML in prose is neutralised. | Escaping is defensive text handling, not a full Markdown sanitiser; review output in a viewer you trust. |
| F-08, F-09 | Fixed | `validate_package` checks shape, types, enums, id format and uniqueness, list sizes and string lengths, and no longer raises on malformed input. Output files are written only from fixed language and platform allowlists through a helper that refuses paths outside the package directory, and `package.json` keeps only known keys. The model response size is capped and truncated or invalid responses fail with a clear message. | There is no separate JSON Schema document; the rules live in `engine.py`. |
| F-10 | Fixed | `tests.yml` has `permissions: contents: read`, `persist-credentials: false`, `timeout-minutes: 10`, and actions are pinned to commit SHAs (checkout v4.4.0, setup-python v5.6.0); Dependabot keeps them current. | Default `GITHUB_TOKEN` scope and branch protection are GitHub settings and could not be checked. Future model-calling workflows still need an environment-protected secret. |
| F-11 | Partly fixed | `.gitignore` covers `.env.*` (except `.env.example`), keys, `*.egg-info/`, `dist/`, `build/`; added Dependabot (actions, pip), `CODEOWNERS` and `SECURITY.md`. | Owner actions: enable GitHub secret scanning and push protection, CodeQL (default setup) and branch protection; run a full-history `gitleaks` scan; pin the build backend. |
| F-12 | Fixed | Model API HTTP errors report only the status and a sanitised error code, never the response body. CLI errors, per-feed errors and validation messages are redacted for keys and bearer tokens and stripped of control characters. `OPENAI_TIMEOUT_SECONDS` is range checked. | No `--debug` mode; verbose diagnostics are intentionally unavailable. |
| F-14       | Fixed        | Trend report now written with real newlines.                                                                                                                                                                                                                                                                |                                                                                                                                                             |
| F-15 | Mostly fixed | 64 tests cover base URL, redirects, claim policy, prompt fencing, RSS ingest, trend limit, schema, rendering, fetcher limits and redirect checks, DTD rejection and error redaction. | No live feed or model integration tests; no tests for the GitHub workflows. |

### Side effects and new observations

- **CISA feed.** The original CISA URL returned HTTP 403 for automated requests (reported by another agent, not independently verified). The feed now goes through a Google News search and is named "CISA advisories (via Google News)" with `trust: discovery_only`. This means **no CISA item can verify a claim**; advisories must be linked manually from cisa.gov. Keeping `primary_or_institutional` on an aggregator link would have reintroduced F-03, and `tests/test_security.py` now guards against that.
- **`certifi`.** `rss.py` sets `SSL_CERT_FILE` from `certifi` when it is installed. This only selects a CA bundle and does not disable TLS verification. `certifi` is not a declared dependency.
- **Publishing checklist (process, not code).** A different branch (`origin/audit_media_production_system`, commit `a29cc8c`) contains `operations/PUBLISHING_CHECKLIST.md` with nearly every box ticked, including "Human approval recorded" and items that cannot have happened before the video was recorded. That commit was not merged here. It confirms F-03's conclusion that the human gate is only as strong as the people who tick it: checklist entries should be completed by the human reviewer, not generated.

---

## 1. Executive summary

The repository is a small, single-author, zero-runtime-dependency CLI (`production_engine/`, about 300 lines of Python). It pulls RSS feeds, builds a prompt, sends it to an OpenAI-compatible chat endpoint, validates the JSON reply and writes Markdown "draft" packages for human review.

**No hardcoded secrets, no secrets in Git history, no `subprocess`/`eval`/`pickle`/`yaml` usage, and no user-controlled path traversal were found.** TLS verification is not disabled. The `.env` file is git-ignored. The project has no third-party runtime dependencies, which removes most of the supply-chain surface. The documented process also requires human approval before publication.

The weaknesses are concentrated in one area: **the trust boundary between untrusted external content (RSS, LLM output) and the controls that are supposed to guarantee editorial integrity.** There are no Critical or High findings. There are **4 Medium**, **6 Low** and **3 Informational** findings.

| ID   | Title                                                              | Severity (est.)  | Status                                          |
| ---- | ------------------------------------------------------------------ | ---------------- | ----------------------------------------------- |
| F-01 | `OPENAI_BASE_URL` is unvalidated and the API key follows redirects | Medium           | Confirmed code path, conditional exploitability |
| F-02 | RSS content is injected unfenced into the LLM prompt               | Medium           | Confirmed code path                             |
| F-03 | "VERIFIED" claim control can be satisfied by any RSS lead          | Medium           | Confirmed                                       |
| F-04 | Feed-controlled ranking and unbounded fields feed the prompt       | Medium (low end) | Confirmed                                       |
| F-05 | Redirects and schemes are unrestricted in outbound feed fetches    | Low              | Potential (URLs are static today)               |
| F-06 | XML parsed with stdlib `ElementTree`, no DOCTYPE rejection         | Low              | Potential, depends on libexpat version          |
| F-07 | Feed and LLM URLs are not scheme-validated, Markdown is unescaped  | Low              | Confirmed code path, impact limited             |
| F-08 | LLM-controlled dictionary keys are used as filenames               | Low              | Potential, not exploitable as written           |
| F-09 | LLM output validation is shallow, with no schema, types or limits  | Low              | Confirmed                                       |
| F-10 | GitHub Actions: no `permissions:`, tag-pinned actions, no timeout  | Low              | Confirmed                                       |
| F-11 | No secret, dependency or code scanning, and weak ignore rules      | Low              | Confirmed                                       |
| F-12 | Upstream error bodies are echoed to stderr                         | Low              | Potential                                       |
| F-13 | `.env` loader and Git metadata observations                        | Info             |                                                 |
| F-14 | Literal `\n` written into the trend Markdown (functional bug)      | Info             | Confirmed                                       |
| F-15 | Security tests are absent                                          | Info             | Confirmed                                       |

**Overall risk (today): Low to Moderate.** The tool is run locally by its owner, produces drafts only, and a human gate exists. **Risk becomes Moderate to High if the tool is automated** (the docs already describe scheduled and manual GitHub workflows). In that case F-01, F-02, F-03 and F-10 combine: untrusted feed text steers an LLM, using a repository secret, in a workflow with default token permissions. The "human approval" control is a checklist in a generated file, not an enforced gate.

---

## 2. Scope and methodology

### In scope

The ten areas in the request: credentials, SSRF/outbound HTTP, RSS/XML parsing, prompt injection, JSON/output validation, filesystem operations, dependencies, GitHub Actions, Git-history secrets and logging.

### Files reviewed in full

`production_engine/engine.py`, `rss.py`, `cli.py`, `__init__.py`, `__main__.py`, `config/sources.json`, `config/.env.example` (values redacted when read), `.github/workflows/tests.yml`, `.gitignore`, `pyproject.toml`, `tests/test_engine.py`. `README.md` and `docs/AI_PRODUCTION_SYSTEM.md` were grepped for security-relevant claims. The other Markdown files are content and templates and were not reviewed in depth.

### Methods

1. Manual data-flow tracing of every untrusted input: RSS/XML, LLM response, env vars, CLI args and local files.
2. Repository inventory: `git ls-files` and `.github/` contents, searched for dependency manifests, lockfiles and scanning configuration (none found).
3. Git history review across all refs: pickaxe search (`git log --all -G`) for key, token, password and `Bearer` patterns, and a scan of every file name ever added for `.env`, `.pem` and `.key`. Each hit was inspected.
4. Environment check: the local venv Python version and its libexpat version.
5. Inspection of the generated artefact `research/trends/2026-11-05.md` to confirm behaviour (see F-14).

No credential values were printed. The `.env.example` key field was checked by length and prefix only: it is a short placeholder and not a real key.

### Out of scope or not performed

See section 4 (Limitations).

---

## 3. Findings

### F-01: `OPENAI_BASE_URL` is unvalidated and the API key follows redirects

**Severity:** Medium (estimated). CVSS 4.0 vector sketch: `AV:L/AC:L/AT:P/PR:L/UI:A/VC:H/VI:N/VA:N/SC:N/SI:N/SA:N`.
**Status:** The code path is confirmed. Exploitation needs control of the environment or `.env`, so it is conditional.

**Evidence**

- `production_engine/engine.py:39`: `base = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")`. There is no scheme, host or allowlist check.
- `engine.py:43`: the `Authorization: Bearer <key>` header is attached to a request to `base + "/chat/completions"`.
- `engine.py:45`: `urllib.request.urlopen` is called with the default opener. It accepts `http://`, `ftp://` and `file://` URLs, and it follows 301/302/303 redirects to any host. Python's `HTTPRedirectHandler` copies the original request headers (minus `Content-*`) to the redirect target, so `Authorization` is not stripped on cross-host redirects.
- `production_engine/cli.py:14-22,54`: `load_dotenv()` loads `ROOT/.env` with `os.environ.setdefault`, so a variable already present in the environment wins over `.env`.
- The prompt body also carries the brand guide, policy and idea text (`engine.py:42`), which would go to the same host.

**Answer to the investigated question:** yes, if `OPENAI_BASE_URL` points at (or is redirected to) an untrusted host, the API key and prompt are sent to it, in plaintext for `http://`. Nothing in the code prevents this. Whoever can set that variable is already inside the trust boundary of the key holder, so this is not remote exploitation by itself. Realistic paths are:

- a poisoned shell profile, CI variable or shared `.env`;
- copy-paste of a "setup" snippet from an untrusted source;
- a compromised or misconfigured OpenAI-compatible gateway/proxy that answers with a 30x.

**Impact:** API key disclosure, plus disclosure of prompt content, and spend on the victim's account.

**Remediation**

- Require `https` and validate the host against an allowlist (default `api.openai.com`). Require an explicit opt-in flag such as `ALLOW_CUSTOM_OPENAI_BASE_URL=1` for other hosts, and log the host in use (never the key).
- Use a custom opener with a redirect handler that raises on redirects for this call (`HTTPRedirectHandler.redirect_request` returning `None`).
- Reject `file:` and `ftp:` explicitly.
- In CI, store the key as an environment-scoped secret and hard-code the base URL in the workflow.

---

### F-02: RSS content is injected unfenced into the LLM prompt (indirect prompt injection)

**Severity:** Medium (estimated). Integrity impact on drafted content. No exfiltration channel or tool-calling was found.
**Status:** Confirmed code path. Actual model behaviour was not tested.

**Evidence**

- `rss.py:36-41,47-51`: `title` and `summary` come straight from third-party XML. Only HTML tags are stripped (`clean_html`, `rss.py:15-16`). Imperative text is untouched.
- `engine.py:31`: `json.dumps(trends)` is concatenated into the same user message as the instructions (`engine.py:29-32`). There are no delimiters, no "treat as data" framing beyond the label "discovery only, not proof", and no separate message role.
- Sources of attacker-influenced text: the four fixed feeds, plus four Google News search queries (`sources.json:29-46`, `rss.py:62-67`). Google News aggregates headlines from arbitrary publishers, so anyone who can publish a news-like page can get text into the lead list.

**Answer to the investigated question:** yes, RSS text reaches the model as part of the instruction context, so it can attempt to inject instructions.

**Mitigating factors (confirmed in code)**

- The model has no tools and no network or filesystem access.
- Output is only written as draft files (`engine.py:80-113`).
- `cli.py:65-72` resets any source URL that is not in the trend list.
- Generated files carry "DRAFT" banners and review checklists.

**Impact:** A malicious headline can steer the narration, captions, CTA or hashtags, or change claim statuses (see F-03). Misinformation or unwanted promotional content could reach a draft, and would pass if the reviewer does not read carefully.

**Remediation**

- Wrap leads in explicit delimiters with a per-run random boundary, and state in the system message that content inside is untrusted data and never instructions. Move the data to a separate message.
- Truncate and normalise titles, and strip control characters.
- Prefer `trust in {primary, primary_or_institutional}` leads, and treat `discovery_only` leads as lower weight.
- Add deterministic post-checks, because the prompt itself cannot enforce anything: URL allowlist, banned-phrase checks, status downgrade rules (F-03).
- Keep a hard human approval step, enforced outside the model.

---

### F-03: The "VERIFIED" control can be satisfied by any RSS lead

**Severity:** Medium (estimated). Integrity of the fact-check policy.
**Status:** Confirmed.

**Evidence**

- `engine.py:70-76`: a claim is accepted as `VERIFIED` if at least one of its `source_ids` matches _any_ source `id` in the model's own `sources` list.
- `cli.py:65-72`: sources whose URL is not in the trend list are blanked and their claims downgraded. This is the only deterministic check. A source whose URL _is_ a trend URL stays, whatever its `source_trust`.
- `rss.py:63-67`: Google News items are labelled `discovery_only`, but `source_trust` is never read after discovery. Aggregator redirect URLs (`news.google.com/rss/articles/...`, present in `research/trends/2026-11-05.json`) therefore count as valid "verified" sources.
- `title`, `publisher` and `published_at` in each source are model-written and never compared to the real lead. A real URL can be paired with a false publisher or date.
- `cli.py:70-72` downgrades only claims whose source was unknown. A claim citing one known and one unknown source stays `VERIFIED`.

**Impact:** The editorial control meant to stop unverified claims from being presented as verified depends on the model's honesty. Combined with F-02, a poisoned headline could cause a false claim to be labelled VERIFIED with a plausible-looking link.

**Remediation**

- In code, cap `VERIFIED` at claims where _every_ cited source maps to a lead with `source_trust in {primary, primary_or_institutional}`. Downgrade everything else.
- Overwrite `title`, `publisher`, `published_at` and `url` from the matching lead and ignore the model's version.
- Never accept aggregator URLs as proof.
- Do not let the model emit `VERIFIED` at all. Set it only after the human review step.

---

### F-04: Feed-controlled ranking and unbounded fields feed the prompt

**Severity:** Medium, low end (estimated). Integrity and cost/availability.
**Status:** Confirmed.

**Evidence**

- `rss.py:36-37`: `title` and `link` have no length cap. Only `summary` is capped at 1200 chars (`rss.py:39,49`). A feed may legitimately be up to 3 MB (`rss.py:32`), so a single title can be megabytes. `engine.py:25,31` then puts the first `limit` items into the prompt unchanged.
- `rss.py:50`: the Atom `updated` value is taken as a raw string. The RSS path validates dates (`rss.py:18-27`), but the Atom path does not.
- `rss.py:83`: items are sorted by that string, descending. A value like `"zzzz"` sorts first and the item is always in the top-N sent to the model.
- `rss.py:76-81`: unparseable dates give `stamp = 0`, and such items are kept forever as `undated`, never filtered by the `--days` window.
- `engine.py:22-25`: `latest_trends` picks the lexicographically last `*.json` in `research/trends/` with no freshness or integrity check.
- `cli.py:42`: `--trend-limit` is not range-checked (negative values slice from the end). This is local-user input only.

**Impact:** A feed (or a Google News result) can claim priority slots in the model's context, bloat the prompt (cost, API errors) and keep stale or hostile items alive indefinitely. This amplifies F-02.

**Remediation:** cap `title`/`url` lengths (for example 300 and 2048); validate and normalise dates for both formats and drop items with unparseable dates (or rank them last); sort on a parsed timestamp; bound `--trend-limit` (for example 1–50); and check that the chosen trend file is recent.

---

### F-05: Redirects and schemes are unrestricted in outbound feed fetches (SSRF-class)

**Severity:** Low (estimated). **Status:** Potential. No attacker-controlled URL reaches the fetcher today.

**Evidence**

- `rss.py:30-31`: `urllib.request.urlopen(req)` with the default opener: follows redirects, including to `http://` (downgrade), internal addresses such as `169.254.169.254` or RFC1918 hosts, and `ftp://`.
- `rss.py:57-59`: feed URLs come from the repository file `sources.json`, and Google News URLs are built with `urllib.parse.quote` on static queries (`rss.py:63`). There is no CLI/env path to inject a URL.
- `rss.py:31-32`: the timeout (20 s) applies to each socket operation, not the whole transfer. A slow server can drip bytes up to the 3 MB cap and hold the process for a long time.
- Response data is only kept if it parses as RSS/Atom, so blind SSRF reads are limited to responses that happen to be valid feeds.

**Answer to the investigated question:** redirects can bypass any URL restriction, but there is currently no URL restriction to bypass, and no untrusted input selects the starting URL. This becomes a real SSRF if feed URLs ever become configurable (CLI flag, user-supplied OPML, pull-request-editable config running in CI with network access to internal services).

**Remediation:** use an opener that re-validates each redirect hop (scheme `https` only; resolve the host and reject loopback, link-local and private ranges); enforce a wall-clock deadline for the whole fetch; keep `sources.json` changes under code review (CODEOWNERS).

---

### F-06: XML parsed with stdlib `ElementTree`, no DOCTYPE rejection

**Severity:** Low (estimated). **Status:** Potential. Depends on the Python and libexpat build.

**Evidence**

- `rss.py:33`: `ET.fromstring(raw)` on untrusted bytes.
- `rss.py:32`: the 3,000,000-byte read cap is a good control. A larger body is truncated and fails to parse.
- `ElementTree` does not fetch external entities, so classic XXE file/URL reads were not found. Entity-expansion ("billion laughs") protection is provided by libexpat 2.4.0 and later. The local venv reports libexpat `2.8.0.5`, which has it. `pyproject.toml:9` allows Python >=3.10, and older distro builds with an older libexpat may not.
- `ET.fromstring` accepts `<!DOCTYPE>`/`<!ENTITY>`, which feeds never need.

**Impact:** Possible CPU/memory exhaustion on an old runtime. Low likelihood with the current feed list.

**Remediation:** reject any payload containing `<!DOCTYPE` or `<!ENTITY` before parsing (cheap, no dependency), or use `defusedxml` and accept the dependency. Document a minimum libexpat/Python version.

---

### F-07: URLs from feeds are not scheme-validated, and Markdown is not escaped

**Severity:** Low (estimated). **Status:** Confirmed code path, limited impact.

**Evidence**

- `rss.py:37,47`: `link` is accepted as any non-empty string (`javascript:`, `data:`, `file:`, spaces, `)`).
- `cli.py:65-69`: the URL allowlist consists of those same strings, so an unsafe URL on a lead passes as "known".
- `engine.py:92`: `[{title}]({url})` is written into `research_brief.md` with no escaping. `engine.py:89` and `engine.py:99-110` also write model/feed text into Markdown unescaped (only the storyboard table escapes `|`, `engine.py:105`).
- `rss.py:92-93`: trend Markdown contains the same unescaped values.

**Impact:** Depends on the viewer. GitHub and VS Code preview sanitise `javascript:` links, but other Markdown renderers or downstream tooling may not. Markdown/HTML injection can also alter how a draft looks to a reviewer.

**Remediation:** allow only `http`/`https` URLs with a hostname at ingest time (`urllib.parse.urlsplit`); percent-encode `)` and spaces; escape Markdown control characters in titles and captions.

---

### F-08: LLM-controlled dictionary keys are used as filenames

**Severity:** Low (estimated). **Status:** Potential. Not exploitable as written, but fragile.

**Evidence**

- `engine.py:109-111`: `for platform, details in data.get("platform_variants", {}).get(lang, {}).items(): ... (pub / f"{lang}-{platform}.md").write_text(...)`. `platform` is a key from model output. `validate_package` checks only three expected keys (`engine.py:65-67`) and does not reject extra ones.
- A key such as `../../x` produces `id-../../x.md`. The first component `id-..` is a directory that does not exist, and `write_text` does not create parents, so the write fails with `FileNotFoundError`. The `{lang}-` prefix therefore blocks classic traversal. On Windows a key containing `:` could address an NTFS alternate data stream.
- Other filesystem use is safe. `read_idea` (`engine.py:11-18`) only matches names returned by `glob("*.md")` in `content/ideas` and never builds a path from the identifier. The output directory is created with `exist_ok=False` (`engine.py:83`) and its name comes from an existing file stem. `--root` (`cli.py:39,43`) is a trusted local argument.

**Impact:** Currently a crash at worst. Any later refactor (for example dropping the prefix or adding `mkdir(parents=True)`) would turn this into arbitrary file write.

**Remediation:** iterate only over the fixed platform allowlist `("tiktok", "instagram_reels", "youtube_shorts")`. Add a final containment check: `resolved.is_relative_to(out.resolve())`.

---

### F-09: LLM output validation is shallow (no schema, types or limits)

**Severity:** Low (estimated). **Status:** Confirmed.

**Evidence**

- `engine.py:54-77`: checks key presence, a few truthy values, slide count and claim status. It does not check types (a list where a dict is expected raises `AttributeError`, which `cli.py:77-79` reports as a generic error), string lengths, hashtag format, URL format, ID uniqueness or unknown extra keys. `source_ids` referencing unknown IDs is tolerated unless the claim is `VERIFIED`.
- `engine.py:46,50-51`: the HTTP response body is read without a size limit and parsed without checking `finish_reason`. A truncated completion would only surface as a JSON error.
- `engine.py:84`: the full unvalidated `data` object is persisted to `package.json`, including any extra keys the model added.
- `engine.py:41`: `int(os.getenv("OPENAI_TIMEOUT_SECONDS"))` has no bounds and a bad value raises a raw `ValueError`.
- No JSON Schema exists in the repository. `docs/CONTENT_PACKAGE_DATA_MODEL.md` describes a model, but code does not enforce it.

**Impact:** Malformed or hostile output can crash the run or put unexpected content into files. This is also the root cause that makes F-03 and F-08 possible.

**Remediation:** define a strict schema (stdlib dataclasses/manual checks, or `jsonschema`/`pydantic` if a dependency is acceptable) with `additionalProperties: false`, string length caps, enums and URL patterns. Validate _after_ the deterministic sanitisation step. Cap the response read size.

---

### F-10: GitHub Actions, no explicit permissions and no hardening

**Severity:** Low today (no secrets used). It would rise to Medium or High once model-calling workflows exist. **Status:** Confirmed.

**Evidence** (`.github/workflows/tests.yml`)

- Lines 1-20 have no `permissions:` key, so the workflow inherits the repository or organisation default `GITHUB_TOKEN` scope. That default can be read/write on older repositories. Whether it is restricted could not be verified from the repository alone.
- Lines 13-14: `actions/checkout@v4` and `actions/setup-python@v5` are pinned to mutable tags, not commit SHAs. `checkout` also persists the token in the local git config by default.
- No `timeout-minutes` and no `concurrency`.
- Line 5: runs on `push` to any `feature/**` branch.
- Line 6: the trigger is `pull_request` (not `pull_request_target`), which is the safe choice for untrusted forks. No secrets are referenced anywhere.
- Line 18: `pip install -e .` resolves `setuptools>=68` from PyPI unpinned and without hashes (`pyproject.toml:2`).
- `docs/AI_PRODUCTION_SYSTEM.md:63` describes "scheduled trend discovery, manual package generation" workflows that do not exist in the repository. When added, they would use `OPENAI_API_KEY` as a secret and combine it with the issues in F-01 to F-04.

**Remediation:** add top-level `permissions: contents: read`; pin actions to full SHAs (Dependabot can update them); set `persist-credentials: false` on checkout and `timeout-minutes`; for future model workflows use `workflow_dispatch` or `schedule` only, an environment with required reviewers for the secret, no fork access, and a hard-coded base URL.

---

### F-11: No secret, dependency or code scanning, and weak ignore rules

**Severity:** Low (estimated). **Status:** Confirmed.

**Evidence**

- `git ls-files` contains no `dependabot.yml`, CodeQL workflow, gitleaks/trufflehog config, `pre-commit` config, `SECURITY.md`, `CODEOWNERS`, lockfile or `requirements*.txt`. The only workflow is `tests.yml`. GitHub-side settings (secret scanning, push protection, branch protection) could not be inspected.
- `.gitignore:1-8`: covers `.env` and `.venv/`, but not `.env.*`/`*.env`, `*.pem`, `*.key`, `*.egg-info/`, `dist/` or `build/`. `git status` currently shows `digital_frontier_production.egg-info/` as untracked, so it could be committed by accident.
- Positive: `pyproject.toml:10` declares `dependencies = []`. The runtime has no third-party code to compromise or audit. Only the build backend (`setuptools>=68`) is external.
- Positive: generated content (`content/production/*`, `research/trends/*.json|md`) is ignored, so scraped third-party text is not committed by default.

**Remediation:** enable GitHub secret scanning and push protection, add `gitleaks` (pre-commit and CI), add Dependabot for `github-actions` and `pip`, add CodeQL for Python, pin the build backend (`setuptools==<x>`) or build in a pinned environment, extend `.gitignore`, and add `SECURITY.md` and CODEOWNERS covering `production_engine/`, `sources.json` and `.github/`.

---

### F-12: Upstream error bodies are echoed to stderr

**Severity:** Low (estimated). **Status:** Potential.

**Evidence**

- `engine.py:47-49`: on `HTTPError`, up to 1000 characters of the server's response body are put in the exception message.
- `cli.py:77-79`: `print(f"Error: {exc}", file=sys.stderr)` for any exception.
- API providers often echo parts of the request in 4xx messages (for example, authentication errors can include a masked key fragment or the model name). I did not trigger a live error, so this is an assumption about provider behaviour. A custom `OPENAI_BASE_URL` (F-01) fully controls what text appears.
- `rss.py:61,66`: per-feed errors are truncated to 300 characters and stored in the git-ignored trend JSON. No credential is involved.
- The API key itself is never logged, printed or interpolated into an exception message in the code reviewed. There is no `logging` usage.

**Impact:** Possible small credential-adjacent disclosure into CI logs or terminals.

**Remediation:** log only status code and a short, sanitised error code/type. Redact anything matching the key or `Bearer` patterns. Keep verbose detail behind an explicit `--debug` flag.

---

### F-13 (Info): `.env` loader and Git-history observations

**`.env` loader, `cli.py:14-22`**

- Existing environment variables beat `.env` (`setdefault`), which is correct for CI but is the mechanism in F-01.
- It does not parse `export KEY=...`. It strips quotes naively.
- It reads `ROOT/.env` (the package location), not `--root`.
- No file-permission check.
- `.env.example` sits in `production_engine/config/`, which differs from the usual repo root and is easy to miss.
- It contains only a short placeholder key (17 characters, no provider prefix) and the default OpenAI URL.

**Git history**

- Scope: all local refs (`main`, `origin/main`, `origin/feature/ai-content-production-system`, two local audit branches), about 40 commits, one author.
- A pickaxe search for key/secret/token/password/`Bearer` patterns matched only the commits adding `engine.py` and `.env.example`. Both were inspected: no credential value.
- No `.env`, `.pem` or `.key` file was ever added.
- Commit metadata contains a personal e-mail address (not reproduced here). This is a privacy note only.
- A pattern search is not a substitute for a dedicated scanner (see Limitations).

### F-14 (Info): Literal `\n` written into the trend Markdown

`rss.py:94` uses `"\\n".join(lines)`, which joins with a backslash and `n` rather than a newline. The generated `research/trends/2026-11-05.md` confirms this: the whole report is on one line. This is a functional bug, not a vulnerability, but it makes the human review artefact hard to read, which weakens a control the process relies on.

### F-15 (Info): Security tests are absent

`tests/test_engine.py` has three tests (`clean_html`, `parse_date`, empty `validate_package`). Nothing covers `call_llm`, URL/redirect handling, the claim-downgrade logic in `cli.py`, rendering, or malicious feed input. CI only runs `unittest`. Regressions in any control above would not be caught.

---

## 4. False positives and limitations

### Checked and not reported as vulnerabilities

| Concern                                             | Conclusion                                                                                                                                                         |
| --------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Hardcoded API keys or tokens                        | None found in code, config or history. `.env.example` is a placeholder.                                                                                            |
| Command injection / unsafe deserialisation          | No `subprocess`, `os.system`, `eval`, `exec`, `pickle` or YAML loading in the package.                                                                             |
| Path traversal via `--idea`                         | Not possible. The identifier only filters `glob("*.md")` results in `content/ideas` (`engine.py:12-13`). An empty or short identifier yields an "ambiguous" error. |
| XXE / external entity retrieval                     | `ElementTree` does not resolve external entities. See F-06 for the residual expansion risk.                                                                        |
| TLS verification                                    | Not disabled. Default `urllib` certificate verification applies.                                                                                                   |
| `pull_request_target` or secret use in the workflow | Not used. The trigger is plain `pull_request` and no secrets are referenced.                                                                                       |
| User-controlled outbound URL                        | None exists today. See F-05.                                                                                                                                       |
| Large feed bodies                                   | Mitigated for the body size (3 MB cap, `rss.py:32`). Per-field limits are missing (F-04).                                                                          |

### Limitations

- **Static review only.** No live feed fetch, no live API call, and no proof-of-concept exploit was executed. Model susceptibility to the injection in F-02 is inferred from the prompt structure and not demonstrated.
- **Sandbox unavailable.** The terminal sandbox could not start (WSL failed), so the read-only `git`/`grep`/`find` commands ran on the host shell. No write, network or destructive command was run. The only file created is this report (and its `reports/` directory).
- **No dedicated scanners.** `gitleaks`, `trufflehog`, `pip-audit`, `bandit`, `semgrep` and CodeQL were not run (not installed, no network). Git-history coverage relies on pattern search and file-name review of local refs.
- **GitHub settings not visible.** Default `GITHUB_TOKEN` permissions, secret scanning, push protection, branch protection and required reviews could not be checked.
- **Content files** (`docs/`, `templates/`, `content/`, `operations/`) were reviewed only via targeted search. Their guidance (for example the SOP and checklists) was not validated against practice.
- **Single-environment check.** The libexpat version was checked on the local venv only. CI uses Python 3.11 on `ubuntu-latest`, which was not inspected.
- **CVSS values** are estimates and exact scores were not calculated.

---

## 5. Prioritised remediation roadmap

| Priority                                               | Action                                                                                                                                              | Findings   | Effort |
| ------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------- | ---------- | ------ |
| **P0, before any automation or CI use of the API key** | Restrict `OPENAI_BASE_URL` to `https` plus an allowlist, and block redirects on the model call                                                      | F-01       | S      |
| P0                                                     | Add `permissions: contents: read`, pin actions by SHA, `persist-credentials: false`, `timeout-minutes`                                              | F-10       | S      |
| P0                                                     | Enable GitHub secret scanning and push protection. Run `gitleaks` once over the full history.                                                       | F-11, F-13 | S      |
| **P1**                                                 | Make `VERIFIED` deterministic: only primary-trust leads, overwrite source metadata from the lead, never accept aggregator links                     | F-03       | M      |
| P1                                                     | Fence untrusted lead text in the prompt, use a separate message, add a "data not instructions" system rule                                          | F-02       | S      |
| P1                                                     | Cap title/url lengths, validate Atom dates, sort on parsed timestamps, bound `--trend-limit`, check trend-file freshness                            | F-04       | S      |
| P1                                                     | Enforce `http`/`https` URL validation at ingest and escape Markdown on output                                                                       | F-07       | S      |
| **P2**                                                 | Strict output schema with types, lengths, enums and `additionalProperties: false`. Use a platform allowlist for filenames plus a containment check. | F-08, F-09 | M      |
| P2                                                     | Redirect-aware, wall-clock-limited fetcher. Reject `<!DOCTYPE`/`<!ENTITY`.                                                                          | F-05, F-06 | M      |
| P2                                                     | Sanitise error output and add a `--debug` flag                                                                                                      | F-12       | S      |
| P2                                                     | Dependabot, CodeQL, pre-commit with gitleaks, extend `.gitignore`, `SECURITY.md`, CODEOWNERS, pin the build backend                                 | F-11       | M      |
| **P3**                                                 | Fix `"\\n".join`. Add security regression tests (malicious feed, redirect, oversize, bad schema, VERIFIED downgrade).                               | F-14, F-15 | M      |
| P3                                                     | Replace the checklist-only approval with an enforced gate, for example a required PR review before generated content is merged or published         | F-02, F-03 | M      |

---

## 6. Security acceptance criteria

The repository can be considered to have addressed this audit when all of the following hold and are covered by automated tests or CI checks:

1. **Credentials**
   - The API key is only ever sent to a host on an explicit allowlist over HTTPS.
   - A test proves a 30x response from the model endpoint is not followed.
   - No credential value appears in logs or error output (test with a canary value).
2. **Outbound HTTP**
   - Every redirect hop is re-validated (scheme, host, non-private IP).
   - Responses have a size cap and a total time limit.
3. **XML and feeds**
   - Payloads containing DOCTYPE/ENTITY are rejected.
   - Feed fields have length caps, and dates and URLs are validated (`http`/`https` only).
4. **Prompt and AI output**
   - Untrusted text is delimited and passed as data.
   - The model output is validated against a strict schema (types, lengths, enums, no extra keys).
   - A test with an injected headline cannot produce a `VERIFIED` claim or a non-lead URL.
5. **Claim integrity**
   - `VERIFIED` is only possible via primary-trust leads, and source metadata is taken from the lead and not the model.
6. **Filesystem**
   - Output filenames derive only from fixed allowlists, with a containment check on every write.
7. **Supply chain**
   - Dependabot, CodeQL, secret scanning with push protection and a `gitleaks` pre-commit/CI job are enabled.
   - The build backend is pinned and `.gitignore` covers `.env.*`, keys and build artefacts.
8. **GitHub Actions**
   - Every workflow declares least-privilege `permissions`, uses SHA-pinned actions and has a timeout.
   - Model-calling workflows run only on `workflow_dispatch` or `schedule`, with an environment-protected secret and no fork access.
9. **Process**
   - Human approval before publication is an enforced, recorded step (not only a Markdown checkbox).

---

## 7. Overall risk assessment

**Current residual risk: Low to Moderate.**

- The attack surface is small. The tool runs locally, has no server component, no third-party runtime dependencies and no state beyond local files. Credentials are kept out of the repository and its history, as far as the checks performed here can show.
- The main weakness is design-level: **external text is treated as trustworthy by the controls that are meant to protect editorial integrity** (F-02, F-03, F-04, F-07, F-09), and the API key has no destination guardrails (F-01).
- If the pipeline is automated as described in the docs, with a repository secret, scheduled runs, default token permissions and unattended generation, the risk becomes **Moderate to High** until the P0 and P1 items are done.

This audit found no more issues than are listed here, but that does not show the repository is secure. The review was static and limited to the code and files read, no dedicated secret/dependency scanners or live tests were run, GitHub-side settings were not inspected, and the model's real behaviour under injection was not measured. The findings should be re-tested after remediation, and re-audited whenever a workflow that uses `OPENAI_API_KEY` is introduced.
