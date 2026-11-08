# pecheriere/homebrew-tap

The Homebrew tap for [warden](https://github.com/pecheriere/warden)'s `warden`
command, the client agents run to ask a warden broker for access. It installs the
release's prebuilt binary for macOS on Apple silicon, and for Linux on x86-64 and
arm64.

```sh
brew install pecheriere/tap/warden
brew trust --formula pecheriere/tap/warden
```

Homebrew loads a formula from a tap outside its own only when you name it in full,
as above, or trust it. The second line lets a plain `brew upgrade` update `warden`
too; without it, upgrade with `brew upgrade pecheriere/tap/warden`.

## What you get

The formula pins each archive of a warden release by its SHA-256, and Homebrew
refuses a download that does not match. Those checksums come from the release's
manifest, which warden's maintainer signs with a key that is not on GitHub. This
repository's CI refuses a formula whose checksums are not the signed ones, checked
against its own copy of the keys in [`release-signers`](release-signers).

To check a binary yourself, follow warden's
[verifying a release](https://github.com/pecheriere/warden/blob/main/docs/verifying-releases.md):
the archive Homebrew downloaded is in `brew --cache pecheriere/tap/warden`.

## How a release gets here

1. The maintainer publishes a warden release, with its signed manifest.
2. warden's `homebrew` workflow waits for the maintainer's approval, then renders
   the formula with `scripts/formula.py` and opens a pull request here. Its token
   can write to this repository only.
3. CI checks the formula against the signed manifest, and installs and tests it
   on each platform.
4. The maintainer reviews and merges it. Until then, nobody's `brew upgrade` sees
   the new version.

## License

MIT or Apache-2.0, at your option, like warden.
