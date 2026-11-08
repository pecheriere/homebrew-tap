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
| `scripts/formula.py` | renders the formula from a release's signed manifest, or checks it; the `bump` workflow runs it too |
| `release-signers` | the warden-release keys the manifest must be signed with, a copy of those in warden's `docs/release-signers` |
| `scripts/scope.py` | CI's `scope` check: a pull request that does more than bump a formula in its `FORMULAE` needs every commit signed by a key in `maintainer-signers` |
| `maintainer-signers` | the maintainer's commit keys |
| `Formula/landfall.rb` | landfall's formula, byte for byte the `landfall.rb` a stable landfall release ships, written by `scripts/landfall.py fetch`; never edit it by hand. It arrives with the first stable release |
| `scripts/landfall.py` | fetches that asset once the release's signed tag and its attestation check out, never going back; CI runs its `check-tree` |
| `landfall-release-signers` | the landfall-release key the release tag must be signed with, a copy of landfall's `crates/cli/assets/release-signers` |
| `scripts/testdata/v0.1.0-rc.1/` | landfall 0.1.0-rc.1's real tag object and its `landfall.rb`, saved as `asset` because check-tree refuses any other file named `landfall.rb`; test fixtures only |
| `.github/workflows/bump.yml` | every hour, renders each formula from its project's latest release and opens an auto-merging pull request for each that changed, one matrix leg per formula |

## Changes

- A change to the formula's shape goes in `TEMPLATE` in `scripts/formula.py`, in
  two pull requests, because CI checks the formula with the script from the base
  commit: first the script alone, then `python3 -I scripts/formula.py render
  <version> Formula/warden.rb`. `bump` checks out `main`, so the next bump uses the
  new shape anyway.
- When warden's release key changes, update `release-signers` in the same way as
  warden's list: add the new key, and keep the old one only while a formula still
  needs it.
- landfall's formula is written by landfall's release workflow, so a change to its
  shape goes in landfall and reaches this repository with the next release. When
  landfall's release key changes, update `landfall-release-signers` the same way
  as `release-signers`, and compare it with the fingerprints in landfall's
  `SECURITY.md`.
- landfall's first formula is added by a commit signed with the maintainer's key:
  run `python3 -I scripts/landfall.py fetch <version> Formula/landfall.rb` for the
  first stable release and commit that file alone. `bump` skips landfall until the
  file exists, and could not add it anyway: `scope` passes an unsigned pull request
  only when it modifies an existing formula. Every later bump is automatic.
- Release candidates are never published here: `scripts/landfall.py` refuses a
  pre-release version and a release GitHub marks as a pre-release. To try the
  checks on one, `fetch --allow-prerelease <version> <file>` writes only a new
  file outside any git repository.
- CI's `landfall-manifest` runs `scripts/landfall.py check-tree` and
  `landfall-release-signers` from the base commit, as `manifest` does for warden,
  and reads the change from git as data. It refuses another file Homebrew could
  take for landfall's formula (`landfall.rb` in any case anywhere else,
  `Formula/**/landfall*.rb`, an `Aliases/` entry named or pointing at landfall, or a
  `formula_renames.json` or `tap_migrations.json` that mentions it), a change that
  deletes the formula (the maintainer
  merges that by hand if it is meant), a changed formula that is not strictly newer
  than the one it replaces, and a version below the highest the formula has had on
  `main`. The change's own script runs only when the base has no part of landfall's
  check, which is the pull request that adds it; a base with some of it but not all
  fails. `check-tree` and `scope` together are the guarantee: `scope` refuses any
  new file without the maintainer's signature, which covers what `check-tree` does
  not look for, such as an external command.
- Once `Formula/landfall.rb` exists, every pull request, warden's bumps included,
  re-verifies it over the network: if landfall's release, its asset or its
  attestation goes away, or GitHub's API is down, `landfall-manifest` fails there.
- Before you push:

  ```sh
  python3 -I -m unittest discover -s scripts -p 'test_*.py'
  python3 -I scripts/formula.py check Formula/warden.rb
  python3 -I scripts/landfall.py check-tree . HEAD . origin/main   # needs gh, logged in, once the formula exists
  python3 -I scripts/scope.py . origin/main HEAD
  brew style pecheriere/tap/warden
  brew audit --strict --online pecheriere/tap/warden
  uvx zizmor@1.31.1 .   # when a workflow or the Dependabot config changes
  ```

- Every commit is signed off with `git commit -s`, as in warden: an agent adds one
  only under the maintainer's configured identity, for work the maintainer asked
  for. The bump commits `bump` makes carry none: a person has not
  made them, and the release they follow is what the maintainer approved.
  `main` takes squash merges only, and commits must be signed.
- Anything but a formula bump needs every commit signed by a key in
  `maintainer-signers`, or `scope` fails. An agent commits with `git commit -s`
  under the maintainer's configured identity and signing key, as in warden, and
  only for work the maintainer asked for. A change to `scripts/`,
  `release-signers`, `landfall-release-signers`, `maintainer-signers` or the workflows changes what lets a bump
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

## Setting up the bump

The maintainer does this once, in the repository's settings:

- Create a fine-grained personal access token for this repository only, with
  read and write access to Contents and Pull requests, and no Workflows
  permission. Store it as `HOMEBREW_TAP_TOKEN` in an environment named
  `homebrew-bump` whose deployment rule allows `main` only. Only `bump`'s `propose`
  job uses that environment.
- Turn on `allow_auto_merge`, so a bump pull request can merge once its checks
  pass.
- In the `main` ruleset, require branches to be up to date before merging, so the
  formula CI compares with is the one the merge replaces, and require these
  checks: `tests`, `manifest`, `scope`, `formula (macos-arm64)`,
  `formula (linux-amd64)`, `formula (linux-arm64)`, `landfall-manifest`,
  `landfall-formula (macos-arm64)`, `landfall-formula (linux-amd64)`,
  `landfall-formula (linux-arm64)`, `zizmor` and `dependency-review`.

When the token expires, `propose` fails: replace it, then rerun the run.

This repository has no package dependencies, so it has no advisory scan beyond
Dependabot's alerts for its actions.
