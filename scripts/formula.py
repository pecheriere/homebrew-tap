"""Writes or checks Formula/warden.rb from a warden release's signed manifest.

Usage:
  python3 -I scripts/formula.py render <version> <formula-file>
  python3 -I scripts/formula.py check <formula-file> [<base-formula-file>]

Both download warden-<version>-SHA256SUMS and its .sig from the published
release, and refuse to go on unless ssh-keygen verifies the signature against
the keys in release-signers, in this repository. They then download each CLI
archive, refuse one whose SHA-256 is not the manifest's, and refuse one that
gh attestation verify does not show was built by warden's release workflow at
the release's tag. render writes the formula for that version. check reads the
version from the formula's first URL, renders the formula again and fails
unless the file is exactly that, so nothing but the version and the signed
checksums can change in a bump.

Neither goes back to an older release: render refuses a version older than the
formula already in <formula-file>, and check one older than <base-formula-file>,
the formula on the branch a pull request merges into.

The bump workflow runs render to open a bump pull request, and this
repository's CI runs check on every pull request, with this script and
release-signers as they are on main. It needs Python 3.11 or later,
ssh-keygen and gh (logged in, or with GH_TOKEN set: gh needs a token even to read
a public repository's attestations), and nothing outside the standard library.
"""

from __future__ import annotations

import hashlib
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from collections.abc import Callable
from pathlib import Path

REPO = "pecheriere/warden"
# The name release-signers lists warden's release keys under. ssh-keygen looks it up
# in that file only: a signature does not carry it.
IDENTITY = "warden-release"
NAMESPACE = "warden-release"
WORKFLOW = f"https://github.com/{REPO}/.github/workflows/release.yml"
SIGNERS = Path(__file__).resolve().parent.parent / "release-signers"
# Each platform the release ships a CLI archive for, in the order the formula
# lists them.
PLATFORMS = ("macos-arm64", "linux-arm64", "linux-amd64")
VERSION = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+")
SHA256 = re.compile(r"[0-9a-f]{64}")

TEMPLATE = """\
# Written by this tap's bump workflow for each warden release, from the release's
# signed manifest: https://github.com/pecheriere/homebrew-tap/blob/main/.github/workflows/bump.yml
# This repository's CI checks every checksum here against that manifest.
class Warden < Formula
  desc "Command-line client for the warden approval broker"
  homepage "https://github.com/pecheriere/warden"
  license any_of: ["MIT", "Apache-2.0"]

  on_macos do
    depends_on arch: :arm64

    on_arm do
      url "{url[macos-arm64]}"
      sha256 "{sha[macos-arm64]}"
    end
  end

  on_linux do
    on_arm do
      url "{url[linux-arm64]}"
      sha256 "{sha[linux-arm64]}"
    end
    on_intel do
      url "{url[linux-amd64]}"
      sha256 "{sha[linux-amd64]}"
    end
  end

  def install
    bin.install "warden"
  end

  test do
    assert_equal "warden #{{version}}", shell_output("#{{bin}}/warden --version").strip
  end
end
"""


class FormulaError(Exception):
    pass


def download_url(version: str, name: str) -> str:
    return f"https://github.com/{REPO}/releases/download/v{version}/{name}"


def archive_name(version: str, platform: str) -> str:
    return f"warden-{version}-{platform}.tar.gz"


class HttpsOnlyRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not newurl.startswith("https://"):
            raise FormulaError(f"refusing a redirect that is not https: {newurl}")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch(url: str) -> bytes:
    if not url.startswith("https://"):
        raise FormulaError(f"refusing a URL that is not https: {url}")
    opener = urllib.request.build_opener(HttpsOnlyRedirects)
    try:
        with opener.open(url, timeout=60) as response:
            return response.read()
    except OSError as error:
        raise FormulaError(f"cannot download {url}: {error}") from error


def verify(manifest: bytes, signature: bytes, signers: Path) -> None:
    """Fails unless the signature is a good warden-release one from a listed key."""
    with tempfile.TemporaryDirectory() as tmp:
        sig = Path(tmp) / "SHA256SUMS.sig"
        sig.write_bytes(signature)
        result = subprocess.run(
            ["ssh-keygen", "-Y", "verify", "-f", str(signers), "-I", IDENTITY, "-n", NAMESPACE, "-s", str(sig)],
            input=manifest,
            capture_output=True,
            check=False,
        )
    if result.returncode != 0:
        raise FormulaError(f"the manifest's signature does not verify against {signers.name}")


def checksums(manifest: bytes, version: str) -> dict[str, str]:
    """The SHA-256 of each platform's CLI archive, from the manifest's lines."""
    wanted = {archive_name(version, platform): platform for platform in PLATFORMS}
    sums: dict[str, str] = {}
    for line in manifest.decode("utf-8").splitlines():
        digest, sep, name = line.partition("  ")
        if not sep or name not in wanted:
            continue
        if not SHA256.fullmatch(digest):
            raise FormulaError(f"the manifest has a malformed checksum for {name}")
        if wanted[name] in sums:
            raise FormulaError(f"the manifest lists {name} twice")
        sums[wanted[name]] = digest
    missing = [archive_name(version, p) for p in PLATFORMS if p not in sums]
    if missing:
        raise FormulaError(f"the manifest has no checksum for {', '.join(missing)}")
    return sums


def attestation_command(path: Path, version: str) -> list[str]:
    return [
        "gh",
        "attestation",
        "verify",
        str(path),
        "--hostname=github.com",
        f"--repo={REPO}",
        # The exact identity of the workflow run that signed it: release.yml at
        # the release's tag, not a pattern that a longer file name could match.
        f"--cert-identity={WORKFLOW}@refs/tags/v{version}",
        f"--source-ref=refs/tags/v{version}",
        "--deny-self-hosted-runners",
    ]


def attest(path: Path, version: str) -> None:
    """Fails unless gh verifies the file's provenance: warden's release workflow at the release's tag."""
    if shutil.which("gh") is None:
        raise FormulaError("gh is not installed, so the attestation cannot be checked")
    try:
        result = subprocess.run(attestation_command(path, version), capture_output=True, check=False)
    except OSError as error:
        raise FormulaError(f"gh attestation verify failed: {error}") from error
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", "replace").strip()
        raise FormulaError(f"gh attestation verify failed for {path.name}: {detail}")


def verify_archives(
    version: str,
    sums: dict[str, str],
    get: Callable[[str], bytes],
    attest_file: Callable[[Path, str], None],
) -> None:
    """Fails unless each archive is the manifest's and its attestation checks out."""
    with tempfile.TemporaryDirectory() as tmp:
        for platform in PLATFORMS:
            name = archive_name(version, platform)
            data = get(download_url(version, name))
            if hashlib.sha256(data).hexdigest() != sums[platform]:
                raise FormulaError(f"{name} does not match the manifest's checksum")
            path = Path(tmp) / name
            path.write_bytes(data)
            attest_file(path, version)


def render(version: str, sums: dict[str, str]) -> str:
    urls = {p: download_url(version, archive_name(version, p)) for p in PLATFORMS}
    return TEMPLATE.format(url=urls, sha=sums)


def signed_formula(
    version: str,
    signers: Path,
    get: Callable[[str], bytes] = fetch,
    attest_file: Callable[[Path, str], None] = attest,
) -> str:
    if not VERSION.fullmatch(version):
        raise FormulaError(f"not a release version: {version}")
    manifest_name = f"warden-{version}-SHA256SUMS"
    manifest = get(download_url(version, manifest_name))
    signature = get(download_url(version, manifest_name + ".sig"))
    verify(manifest, signature, signers)
    sums = checksums(manifest, version)
    verify_archives(version, sums, get, attest_file)
    return render(version, sums)


def formula_version(text: str) -> str:
    match = re.search(r'url "https://github\.com/pecheriere/warden/releases/download/v([0-9.]+)/', text)
    if not match:
        raise FormulaError("the formula has no warden release URL")
    return match.group(1)


def version_key(version: str) -> tuple[int, ...]:
    if not VERSION.fullmatch(version):
        raise FormulaError(f"not a release version: {version}")
    return tuple(int(part) for part in version.split("."))


def refuse_older(version: str, than: Path) -> None:
    if not than.exists():
        return
    current = formula_version(than.read_text(encoding="utf-8"))
    if version_key(version) < version_key(current):
        raise FormulaError(f"refusing to go back from warden {current} to {version}")


def render_file(
    version: str,
    path: Path,
    signers: Path,
    get: Callable[[str], bytes] = fetch,
    attest_file: Callable[[Path, str], None] = attest,
) -> None:
    refuse_older(version, path)
    path.write_bytes(signed_formula(version, signers, get, attest_file).encode("utf-8"))


def check_file(
    path: Path,
    base: Path | None,
    signers: Path,
    get: Callable[[str], bytes] = fetch,
    attest_file: Callable[[Path, str], None] = attest,
) -> str:
    # Bytes, not text: reading text would turn a lone carriage return into a newline.
    data = path.read_bytes()
    version = formula_version(data.decode("utf-8", errors="replace"))
    if base is not None:
        refuse_older(version, base)
    if data != signed_formula(version, signers, get, attest_file).encode("utf-8"):
        raise FormulaError(
            f"{path} is not the formula for {version}'s signed manifest: "
            f"run python3 -I scripts/formula.py render {version} {path} and compare"
        )
    return version


def main(argv: list[str]) -> int:
    try:
        if len(argv) == 3 and argv[0] == "render":
            render_file(argv[1], Path(argv[2]), SIGNERS)
            return 0
        if len(argv) in (2, 3) and argv[0] == "check":
            base = Path(argv[2]) if len(argv) == 3 else None
            version = check_file(Path(argv[1]), base, SIGNERS)
            print(f"{argv[1]} matches the signed manifest of warden {version}")
            return 0
    except FormulaError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(__doc__.split("\n\n")[1], file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
