# pecheriere/homebrew-tap

The Homebrew tap for these commands. Each formula installs the release's prebuilt
binary for macOS on Apple silicon, and for Linux on x86-64 and arm64.

- [warden](https://github.com/pecheriere/warden)'s `warden`, the client agents run
  to ask a warden broker for access:

  ```sh
  brew install pecheriere/tap/warden
  ```

- [landfall](https://github.com/pecheriere/landfall)'s `landfall`, the command line
  for landfall's continuous delivery for self-hosters. Its formula arrives with
  landfall's first stable release; release candidates are never published here.

  ```sh
  brew install pecheriere/tap/landfall
  ```

Naming the formula in full also tells Homebrew to trust it, which it needs for a
tap outside its own. After that, `brew upgrade` updates the command with
everything else.

## What you get

warden's formula pins each archive of a warden release by its SHA-256, and
Homebrew refuses a download that does not match. Those checksums come from the
release's manifest, which warden's maintainer signs with a key that is not on
GitHub. This repository's CI refuses a formula whose checksums are not the signed
ones, checked against its own copy of the keys in
[`release-signers`](release-signers), and one older than the formula it replaces.

To check a binary yourself, follow warden's
[verifying a release](https://github.com/pecheriere/warden/blob/main/docs/verifying-releases.md):
the archive Homebrew downloaded is in `brew --cache pecheriere/tap/warden`.

landfall's formula is the one its release ships, `landfall.rb`, byte for byte.
CI accepts it only if the release's tag carries a good signature from the key in
[`landfall-release-signers`](landfall-release-signers), this repository's own copy,
and GitHub's build provenance attestation shows that landfall's release workflow
built the file, on GitHub's runners, from the commit that tag names. A stolen
GitHub token could run landfall's release workflow, but it could not sign the tag.
CI also refuses a landfall version older than the formula it replaces or than any
landfall version this tap has had, and another file through which Homebrew could
take something else for landfall's formula. That check and `scope`, below,
together keep anything but the verified formula out of a bump.

## How a release gets here

1. The maintainer publishes a release: warden's with its signed manifest,
   landfall's from a signed tag. That is the step a person takes.
2. This repository's hourly `bump` workflow reads each project's latest release,
   writes the formula with this repository's scripts and opens a pull request
   here, with auto-merge on. Its token can write to this repository only.
3. CI checks the formula with the scripts and keys from `main`, and installs and
   tests it on each platform. The pull request merges when every required check
   passes. Nobody reviews it first: the checks are the gate.

Only a change to an existing formula merges that way. Any other change, including
a new or moved formula file, merges only if the maintainer signed each of its
commits with a key in [`maintainer-signers`](maintainer-signers): CI's `scope`
check refuses it otherwise.

So landfall's first formula is added by hand: `bump` skips landfall until
`Formula/landfall.rb` exists, and its pull request would add a file, which
`scope` refuses. A person, or an agent with the maintainer's commit key, runs
`python3 -I scripts/landfall.py fetch <version> Formula/landfall.rb` for the first
stable release and commits the file, signed. Every later bump is automatic.

## License

MIT or Apache-2.0, at your option, like warden and landfall.
