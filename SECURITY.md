# Security policy

This tap decides which binary `brew install pecheriere/tap/warden` and
`brew install pecheriere/tap/landfall` install, so a problem here is a problem in
warden or landfall.

Report vulnerabilities privately through GitHub security advisories, in this
repository (<https://github.com/pecheriere/homebrew-tap/security/advisories/new>),
in warden's (<https://github.com/pecheriere/warden/security/advisories/new>) or in
landfall's (<https://github.com/pecheriere/landfall/security/advisories/new>).
Please do not open a public issue or pull request for a suspected vulnerability.

warden's [security policy](https://github.com/pecheriere/warden/blob/main/SECURITY.md)
and landfall's [security policy](https://github.com/pecheriere/landfall/blob/main/SECURITY.md)
apply here too, each for its own formula: response time, how reports are handled,
credit and supported versions.

landfall's formula is accepted only from a release whose tag is signed by the
landfall-release key, with the fingerprint
`SHA256:NQDx0iXAXnjJDtJz662lf+yEZuX46AZ20/RHcBU0TIk`, the one landfall's
security policy publishes. This repository keeps its own copy of that key in
[`landfall-release-signers`](landfall-release-signers), and
`scripts/landfall.py` checks the tag against it, both when CI checks a formula and
when the `bump` workflow fetches one.
