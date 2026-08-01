# Security Policy

## Supported versions

Only the latest release receives fixes. Tax-rule corrections always land in a
new release rather than a retroactive edit — see CONTRIBUTING.md.

## Reporting a vulnerability

Use GitHub's private vulnerability reporting on this repository
(Security → Report a vulnerability). Please do not open a public issue for
anything exploitable.

Note the threat model: this library computes taxes from figures you supply.
It stores no credentials, makes no network calls, and has zero runtime
dependencies. The most damaging class of defect is a silently wrong tax
figure — if you find one, that IS a security-relevant bug here; report it
with the section/circular that shows the correct treatment.

## Supply chain

- Releases are published to PyPI via GitHub Trusted Publishing (OIDC) — no
  long-lived tokens exist anywhere.
- All GitHub Actions are pinned to full commit SHAs.
- The published wheel contains only `india_tax_guru/` and its license; verify
  with `unzip -l`.
