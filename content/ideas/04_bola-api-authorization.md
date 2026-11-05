# One API Authorization Bug Can Expose Other Users' Data

- Pillar: Cybersecurity
- Status: Evergreen / research required
- Audience: Developers, IT students, security learners

## Editorial angle
Introduce Broken Object Level Authorization (BOLA), also commonly associated with IDOR, using a safe fictional example. Focus on the authorization design flaw and its remediation.

## Key questions
- Why is authentication not enough to protect API objects?
- How can changing an object identifier reveal an authorization weakness?
- Why must the server verify ownership or access rights on every request?
- What negative tests can help detect BOLA?

## Accuracy notes
Use a local lab or fictional data only. Explain object-level authorization checks, deny-by-default behavior, and regression testing. Do not test systems without explicit authorization.
