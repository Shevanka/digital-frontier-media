# Security Policy

## Reporting a vulnerability

Please do not open a public issue for security problems. Use GitHub's private
vulnerability reporting for this repository (Security tab, "Report a vulnerability"),
or contact the repository owner directly.

## Handling of secrets

- `OPENAI_API_KEY` belongs in a local `.env` file (git-ignored) or in a protected CI secret.
  Never commit it, paste it into issues, or put it in generated content.
- If a key may have been exposed, revoke it at the provider first, then clean up.
- The API key is only sent to hosts allowed by `OPENAI_BASE_URL` validation. Custom hosts
  require `ALLOW_CUSTOM_OPENAI_BASE_URL=1` and should be treated as fully trusted.

## Untrusted input

RSS/Atom feeds and model output are untrusted. Generated packages are drafts: every claim
must be verified against its original source and approved by a human reviewer before
publication. Checklists must be completed by that reviewer, not generated.

See `reports/security-audit.md` for the current audit status and open items.
## Overview

Digital Frontier Media is an AI-assisted bilingual technology content production system. It collects external content through RSS feeds, processes research inputs, interacts with Large Language Models (LLMs), and generates editorial production packages.

Security is important to protect the integrity of generated content, API credentials, local files, and the development environment.

This document describes the project's security reporting process and security expectations.

## Supported Versions

Security updates are applied to the latest maintained version on the `main` branch.

| Version | Security Support |
|---|---|
| Latest `main` | Supported |
| Older commits | Not guaranteed |

Users are encouraged to use the latest version and review security-related changes before deploying or running the production engine.

## Reporting a Vulnerability

**Please do not report security vulnerabilities through public GitHub issues or public pull requests.**

If you discover a potential security vulnerability, please report it privately through one of the following channels:

1. Use GitHub's **Report a vulnerability** feature in the repository's Security tab, if private vulnerability reporting is enabled.
2. If private reporting is unavailable, contact the repository maintainer directly through their GitHub profile.

Please include the following information in your report:

- A clear description of the vulnerability.
- The affected component, file, or function.
- The potential security impact.
- Reproduction steps or a minimal proof of concept.
- Relevant logs, screenshots, or request samples, with secrets and personal information removed.
- Suggested remediation, if available.

Do not include real API keys, passwords, access tokens, or other sensitive credentials in your report.

## Response and Disclosure Process

The maintainer will review submitted reports and may request additional information to reproduce or assess the issue.

The handling process generally follows these stages:

1. **Acknowledgment:** The report is received and reviewed.
2. **Validation:** The reported behavior is investigated and its security impact assessed.
3. **Remediation:** An appropriate fix or mitigation is developed.
4. **Verification:** The fix is tested to ensure the issue has been addressed.
5. **Disclosure:** Relevant security information may be disclosed after remediation, where appropriate.

Response and remediation timelines are not guaranteed. They depend on the severity, complexity, and available maintenance resources.

Please allow the maintainer reasonable time to investigate and address a report before publicly disclosing it.

## Security Scope

The following components are considered within the project's security scope:

| Component | Security Considerations |
|---|---|
| `production_engine/` | Input validation, filesystem operations, error handling, and application logic |
| RSS feed discovery | Untrusted external content, URL validation, SSRF, and XML parsing |
| LLM integration | Prompt injection, output validation, and API credential protection |
| Content rendering | Path traversal, file overwrite, and generated content integrity |
| Configuration | Environment variables, secrets, and endpoint validation |
| GitHub Actions | Workflow permissions, dependency integrity, and CI/CD security |
| Dependencies | Known vulnerabilities and software supply-chain risks |

## Security Expectations

### 1. API Credentials and Secrets

- Never commit API keys, passwords, tokens, or private credentials.
- Store sensitive configuration in environment variables or an appropriate secret manager.
- Keep `.env` files out of version control.
- Use HTTPS for external API communication.
- Do not expose credentials in logs, generated content, error messages, or public reports.

### 2. RSS Feeds and External Content

- Treat RSS and Atom feed content as untrusted external input.
- Validate feed URLs before making outbound requests.
- Restrict unsupported URL schemes and unsafe network destinations.
- Apply appropriate response-size and timeout
