# AGENTS.md

Instructions for coding agents (and humans) working on this tap. The README says
what it is and how a release reaches it.

## This is a public repository

Never commit private infrastructure details: hostnames, addresses, user names,
email addresses. Commit messages and pull request descriptions carry no AI
attribution lines (`Co-Authored-By`, session links, "Generated with").

## Layout

| Path | What |
|---|---|
| `Formula/warden.rb` | the formula, written by `scripts/formula.py render`; never edit it by hand |
| `scripts/formula.py` | renders the formula from a release's signed manifest, or checks it; warden's `homebrew` workflow runs it too |
| `release-signers` | the warden-release keys the manifest must be signed with, a copy of those in warden's `docs/release-signers` |

## Changes

- A change to the formula's shape goes in `TEMPLATE` in `scripts/formula.py`,
  followed by `python3 -I scripts/formula.py render <version> Formula/warden.rb`.
  warden's workflow checks out `main`, so the next bump uses it.
- When warden's release key changes, update `release-signers` in the same way as
  warden's list: add the new key, and keep the old one only while a formula still
  needs it.
- Before you push:

  ```sh
  python3 -I -m unittest discover -s scripts -p 'test_*.py'
  python3 -I scripts/formula.py check Formula/warden.rb
  brew style pecheriere/tap/warden
  brew audit --strict --online pecheriere/tap/warden
  uvx zizmor@1.31.1 .   # when a workflow or the Dependabot config changes
  ```

- Every commit is signed off with `git commit -s`, as in warden: an agent adds one
  only under the maintainer's configured identity, for work the maintainer asked
  for. `main` takes squash merges only, and commits must be signed.
- GitHub Actions are pinned to the full commit SHA of a release at least 7 days
  old.

This repository has no package dependencies, so it has no advisory scan beyond
Dependabot's alerts for its actions.
