"""Tests for formula.py, with a throwaway key and no network.

Run: python3 -I -m unittest discover -s scripts -p 'test_*.py'
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
import tempfile
import unittest
import urllib.request
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import formula

VERSION = "1.2.3"
ARCHIVES = {p: f"the {p} archive".encode() for p in formula.PLATFORMS}
SUMS = {p: hashlib.sha256(data).hexdigest() for p, data in ARCHIVES.items()}


def archive_url(version: str, platform: str) -> str:
    return formula.download_url(version, formula.archive_name(version, platform))


def no_attestation(path: Path, version: str) -> None:
    """An attestation check that passes, for tests of something else."""


def manifest_for(version: str, sums: dict[str, str]) -> bytes:
    lines = [f"{'0' * 64}  warden-demo-{version}-linux-amd64.tar.gz"]
    lines += [f"{sums[p]}  warden-{version}-{p}.tar.gz" for p in formula.PLATFORMS]
    lines.append(f"{'1' * 64}  ghcr.io/pecheriere/warden:{version}")
    return ("\n".join(lines) + "\n").encode()


class SignedFormulaTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.key = self.dir / "key"
        subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(self.key)], check=True)
        public = (self.dir / "key.pub").read_text().split()
        self.signers = self.dir / "signers"
        self.signers.write_text(f'{formula.IDENTITY} namespaces="{formula.NAMESPACE}" {public[0]} {public[1]}\n')

    def sign(self, data: bytes, namespace: str = formula.NAMESPACE) -> bytes:
        path = self.dir / "manifest"
        path.write_bytes(data)
        (self.dir / "manifest.sig").unlink(missing_ok=True)
        subprocess.run(
            ["ssh-keygen", "-q", "-Y", "sign", "-n", namespace, "-f", str(self.key), str(path)],
            check=True,
            stdin=subprocess.DEVNULL,
        )
        return (self.dir / "manifest.sig").read_bytes()

    def served(self, manifest: bytes, signature: bytes) -> dict[str, bytes]:
        base = f"https://github.com/pecheriere/warden/releases/download/v{VERSION}/warden-{VERSION}-SHA256SUMS"
        files = {base: manifest, base + ".sig": signature}
        files.update({archive_url(VERSION, p): data for p, data in ARCHIVES.items()})
        return files

    def test_renders_the_signed_checksums(self) -> None:
        manifest = manifest_for(VERSION, SUMS)
        files = self.served(manifest, self.sign(manifest))
        text = formula.signed_formula(VERSION, self.signers, files.__getitem__, no_attestation)
        for platform in formula.PLATFORMS:
            self.assertIn(f'sha256 "{SUMS[platform]}"', text)
            url = f"https://github.com/pecheriere/warden/releases/download/v{VERSION}/warden-{VERSION}-{platform}.tar.gz"
            self.assertIn(f'url "{url}"', text)
        self.assertIn('assert_equal "warden #{version}"', text)
        self.assertEqual(formula.formula_version(text), VERSION)

    def test_refuses_a_changed_manifest(self) -> None:
        manifest = manifest_for(VERSION, SUMS)
        signature = self.sign(manifest)
        changed = manifest_for(VERSION, {**SUMS, "macos-arm64": "f" * 64})
        with self.assertRaisesRegex(formula.FormulaError, "does not verify"):
            formula.signed_formula(VERSION, self.signers, self.served(changed, signature).__getitem__, no_attestation)

    def test_refuses_another_namespace(self) -> None:
        manifest = manifest_for(VERSION, SUMS)
        signature = self.sign(manifest, namespace="git")
        with self.assertRaisesRegex(formula.FormulaError, "does not verify"):
            formula.signed_formula(VERSION, self.signers, self.served(manifest, signature).__getitem__, no_attestation)

    def test_refuses_an_unlisted_key(self) -> None:
        manifest = manifest_for(VERSION, SUMS)
        signature = self.sign(manifest)
        self.signers.write_text("")
        with self.assertRaisesRegex(formula.FormulaError, "does not verify"):
            formula.signed_formula(VERSION, self.signers, self.served(manifest, signature).__getitem__, no_attestation)

    def test_refuses_another_identity(self) -> None:
        manifest = manifest_for(VERSION, SUMS)
        signature = self.sign(manifest)
        self.signers.write_text(self.signers.read_text().replace(formula.IDENTITY, "someone@example.com"))
        with self.assertRaisesRegex(formula.FormulaError, "does not verify"):
            formula.signed_formula(VERSION, self.signers, self.served(manifest, signature).__getitem__, no_attestation)

    def signed_get(self):
        manifest = manifest_for(VERSION, SUMS)
        return self.served(manifest, self.sign(manifest)).__getitem__

    def test_render_file_writes_the_formula(self) -> None:
        path = self.dir / "warden.rb"
        formula.render_file(VERSION, path, self.signers, self.signed_get(), no_attestation)
        self.assertEqual(formula.check_file(path, None, self.signers, self.signed_get(), no_attestation), VERSION)

    def test_render_file_refuses_to_go_back(self) -> None:
        path = self.dir / "warden.rb"
        path.write_text(formula.render("1.10.0", SUMS))
        with self.assertRaisesRegex(formula.FormulaError, "go back from warden 1.10.0 to 1.2.3"):
            formula.render_file(VERSION, path, self.signers, self.signed_get(), no_attestation)
        self.assertIn("1.10.0", path.read_text())

    def test_check_file_refuses_a_hand_edit(self) -> None:
        path = self.dir / "warden.rb"
        formula.render_file(VERSION, path, self.signers, self.signed_get(), no_attestation)
        path.write_text(path.read_text().replace('bin.install "warden"', 'bin.install "warden"\n    system "true"'))
        with self.assertRaisesRegex(formula.FormulaError, "is not the formula"):
            formula.check_file(path, None, self.signers, self.signed_get(), no_attestation)

    def test_check_file_refuses_a_carriage_return(self) -> None:
        path = self.dir / "warden.rb"
        formula.render_file(VERSION, path, self.signers, self.signed_get(), no_attestation)
        path.write_bytes(path.read_bytes().replace(b"\n", b"\r", 1))
        with self.assertRaisesRegex(formula.FormulaError, "is not the formula"):
            formula.check_file(path, None, self.signers, self.signed_get(), no_attestation)

    def test_check_file_refuses_to_go_back(self) -> None:
        path = self.dir / "warden.rb"
        formula.render_file(VERSION, path, self.signers, self.signed_get(), no_attestation)
        base = self.dir / "base.rb"
        base.write_text(formula.render("1.3.0", SUMS))
        with self.assertRaisesRegex(formula.FormulaError, "go back"):
            formula.check_file(path, base, self.signers, self.signed_get(), no_attestation)

    def test_refuses_a_bad_version(self) -> None:
        with self.assertRaisesRegex(formula.FormulaError, "not a release version"):
            formula.signed_formula("1.2.3/../x", self.signers, {}.__getitem__, no_attestation)


    # The archives are downloaded, matched to the manifest and attested before the
    # formula is rendered.

    def attested_refs(self, refs: dict[str, str]):
        """A stand-in for gh: it verifies a file only for the ref its digest was attested at."""
        calls: list[list[str]] = []
        real_run = subprocess.run

        def fake_run(command, **kwargs):
            if command[0] != "gh":
                return real_run(command, **kwargs)
            calls.append(command)
            digest = hashlib.sha256(Path(command[3]).read_bytes()).hexdigest()
            ref = next(a.split("=", 1)[1] for a in command if a.startswith("--source-ref="))
            if refs.get(digest) == ref:
                return subprocess.CompletedProcess(command, 0, b"", b"")
            return subprocess.CompletedProcess(command, 1, b"", b"no matching attestation")

        patches = (
            mock.patch.object(formula.shutil, "which", return_value="gh"),
            mock.patch.object(formula.subprocess, "run", fake_run),
        )
        return calls, patches

    def render(self, get, refs: dict[str, str]) -> str:
        calls, patches = self.attested_refs(refs)
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)
        self.calls = calls
        return formula.signed_formula(VERSION, self.signers, get)

    def test_renders_when_attested(self) -> None:
        refs = {digest: f"refs/tags/v{VERSION}" for digest in SUMS.values()}
        text = self.render(self.signed_get(), refs)
        self.assertEqual(formula.formula_version(text), VERSION)
        self.assertEqual(len(self.calls), len(formula.PLATFORMS))
        command = self.calls[0]
        self.assertEqual(command[:3], ["gh", "attestation", "verify"])
        for flag in (
            "--hostname=github.com",
            "--repo=pecheriere/warden",
            f"--cert-identity=https://github.com/pecheriere/warden/.github/workflows/release.yml@refs/tags/v{VERSION}",
            f"--source-ref=refs/tags/v{VERSION}",
            "--deny-self-hosted-runners",
        ):
            self.assertIn(flag, command)

    def test_refuses_archive_without_attestation(self) -> None:
        refs = {digest: f"refs/tags/v{VERSION}" for digest in list(SUMS.values())[1:]}
        with self.assertRaisesRegex(formula.FormulaError, "no matching attestation"):
            self.render(self.signed_get(), refs)

    def test_refuses_attestation_from_other_ref(self) -> None:
        refs = {digest: "refs/heads/main" for digest in SUMS.values()}
        with self.assertRaisesRegex(formula.FormulaError, "no matching attestation"):
            self.render(self.signed_get(), refs)

    def test_refuses_archive_not_matching_manifest(self) -> None:
        manifest = manifest_for(VERSION, SUMS)
        files = self.served(manifest, self.sign(manifest))
        files[archive_url(VERSION, "linux-arm64")] = b"swapped"
        refs = {digest: f"refs/tags/v{VERSION}" for digest in SUMS.values()}
        with self.assertRaisesRegex(formula.FormulaError, "does not match the manifest"):
            self.render(files.__getitem__, refs)
        self.assertFalse([c for c in self.calls if "linux-arm64" in c[3]])

    def test_refuses_without_gh(self) -> None:
        with (
            mock.patch.object(formula.shutil, "which", return_value=None),
            self.assertRaisesRegex(formula.FormulaError, "gh is not installed"),
        ):
            formula.signed_formula(VERSION, self.signers, self.signed_get())


class ChecksumsTest(unittest.TestCase):
    def test_missing_platform(self) -> None:
        manifest = manifest_for(VERSION, SUMS).replace(b"linux-arm64", b"linux-riscv")
        with self.assertRaisesRegex(formula.FormulaError, "no checksum for warden-1.2.3-linux-arm64"):
            formula.checksums(manifest, VERSION)

    def test_listed_twice(self) -> None:
        manifest = manifest_for(VERSION, SUMS) + f"{'2' * 64}  warden-{VERSION}-linux-amd64.tar.gz\n".encode()
        with self.assertRaisesRegex(formula.FormulaError, "twice"):
            formula.checksums(manifest, VERSION)

    def test_malformed_checksum(self) -> None:
        manifest = manifest_for(VERSION, {**SUMS, "linux-amd64": "XYZ"})
        with self.assertRaisesRegex(formula.FormulaError, "malformed"):
            formula.checksums(manifest, VERSION)

    def test_ignores_other_versions(self) -> None:
        manifest = manifest_for("1.2.4", SUMS)
        with self.assertRaisesRegex(formula.FormulaError, "no checksum"):
            formula.checksums(manifest, VERSION)


class FetchTest(unittest.TestCase):
    def test_refuses_a_redirect_to_plain_http(self) -> None:
        request = urllib.request.Request("https://github.com/x")
        with self.assertRaisesRegex(formula.FormulaError, "redirect that is not https"):
            formula.HttpsOnlyRedirects().redirect_request(request, None, 302, "Found", {}, "http://example.com/x")

    def test_refuses_plain_http(self) -> None:
        with self.assertRaisesRegex(formula.FormulaError, "not https"):
            formula.fetch("http://github.com/pecheriere/warden/releases/download/v1.2.3/x")


class FormulaVersionTest(unittest.TestCase):
    def test_no_url(self) -> None:
        with self.assertRaisesRegex(formula.FormulaError, "no warden release URL"):
            formula.formula_version('url "https://example.com/warden-1.2.3.tar.gz"')



class ReleaseSignersTest(unittest.TestCase):
    def test_every_key_is_listed_under_the_checked_identity(self) -> None:
        lines = [line for line in formula.SIGNERS.read_text().splitlines() if line and not line.startswith("#")]
        self.assertTrue(lines)
        for line in lines:
            self.assertEqual(line.split()[:2], [formula.IDENTITY, f'namespaces="{formula.NAMESPACE}"'])

if __name__ == "__main__":
    unittest.main()
