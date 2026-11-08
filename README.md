# pecheriere/homebrew-tap

The Homebrew tap for [warden](https://github.com/pecheriere/warden)'s `warden`
command, the client agents run to ask a warden broker for access. It installs the
release's prebuilt binary for macOS on Apple silicon, and for Linux on x86-64 and
arm64.

```sh
brew install pecheriere/tap/warden
```

Naming the formula in full also tells Homebrew to trust it, which it needs for a
tap outside its own. After that, `brew upgrade` updates `warden` with everything
else.

## What you get

The formula pins each archive of a warden release by its SHA-256, and Homebrew
refuses a download that does not match. Those checksums come from the release's
manifest, which warden's maintainer signs with a key that is not on GitHub. This
repository's CI refuses a formula whose checksums are not the signed ones, checked
against its own copy of the keys in [`release-signers`](release-signers), and one
older than the formula it replaces.

To check a binary yourself, follow warden's
[verifying a release](https://github.com/pecheriere/warden/blob/main/docs/verifying-releases.md):
the archive Homebrew downloaded is in `brew --cache pecheriere/tap/warden`.

## How a release gets here

1. The maintainer publishes a warden release, with its signed manifest. That is
   the step a person takes.
2. warden's `homebrew` workflow renders the formula with `scripts/formula.py` and
   opens a pull request here, with auto-merge on. Its token can write to this
   repository only, and it can be used only from a workflow run for a release tag.
3. CI checks the formula against the signed manifest, with the script and keys
   from `main`, and installs and tests it on each platform. The pull request
   merges when every check passes.

## License

MIT or Apache-2.0, at your option, like warden.
