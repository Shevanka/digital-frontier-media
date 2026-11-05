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
