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
| `scripts/scope.py` | CI's `scope` check: a pull request that does more than bump a formula in its `FORMULAE` needs every commit signed by a key in `maintainer-signers` |
| `maintainer-signers` | the maintainer's commit keys |

## Changes

- A change to the formula's shape goes in `TEMPLATE` in `scripts/formula.py`, in
  two pull requests, because CI checks the formula with the script from the base
  commit: first the script alone, then `python3 -I scripts/formula.py render
  <version> Formula/warden.rb`. warden's workflow checks out `main`, so the next
  bump uses the new shape anyway.
- When warden's release key changes, update `release-signers` in the same way as
  warden's list: add the new key, and keep the old one only while a formula still
  needs it.
- Before you push:

  ```sh
  python3 -I -m unittest discover -s scripts -p 'test_*.py'
  python3 -I scripts/formula.py check Formula/warden.rb
  python3 -I scripts/scope.py . origin/main HEAD
  brew style pecheriere/tap/warden
  brew audit --strict --online pecheriere/tap/warden
  uvx zizmor@1.31.1 .   # when a workflow or the Dependabot config changes
  ```

- Every commit is signed off with `git commit -s`, as in warden: an agent adds one
  only under the maintainer's configured identity, for work the maintainer asked
  for. The bump commits warden's workflow makes carry none: a person has not
  made them, and the release they follow is what the maintainer approved.
  `main` takes squash merges only, and commits must be signed.
- Anything but a formula bump needs every commit signed by a key in
  `maintainer-signers`, or `scope` fails. An agent commits with `git commit -s`
  under the maintainer's configured identity and signing key, as in warden, and
  only for work the maintainer asked for. A change to `scripts/`,
  `release-signers`, `maintainer-signers` or the workflows changes what lets a bump
  merge by itself: only the maintainer merges one, after reading it.
- `scope` accepts any commit signed by a listed key, and the workflow's token can
  recreate a signed commit and merge pull requests. So a signed branch or pull
  request based on the current `main` can be landed with the token alone: delete
  signed work you do not mean to land, and keep a series that must land together in
  one pull request.
- Dependabot's pull requests change workflows and carry GitHub's signature, so
  `scope` fails them: check them out, commit the same change signed, and open that
  instead.
- GitHub Actions are pinned to the full commit SHA of a release at least 7 days
  old.

This repository has no package dependencies, so it has no advisory scan beyond
Dependabot's alerts for its actions.
