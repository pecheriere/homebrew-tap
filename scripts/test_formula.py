"""Tests for formula.py, with a throwaway key and no network.

Run: python3 -I -m unittest discover -s scripts -p 'test_*.py'
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import formula

VERSION = "1.2.3"
SUMS = {p: f"{i:x}" * 64 for i, p in enumerate(formula.PLATFORMS, start=10)}


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
        subprocess.run(["ssh-keygen", "-q", "-Y", "sign", "-n", namespace, "-f", str(self.key), str(path)], check=True)
        return (self.dir / "manifest.sig").read_bytes()

    def served(self, manifest: bytes, signature: bytes) -> dict[str, bytes]:
        base = f"https://github.com/pecheriere/warden/releases/download/v{VERSION}/warden-{VERSION}-SHA256SUMS"
        return {base: manifest, base + ".sig": signature}

    def test_renders_the_signed_checksums(self) -> None:
        manifest = manifest_for(VERSION, SUMS)
        files = self.served(manifest, self.sign(manifest))
        text = formula.signed_formula(VERSION, self.signers, files.__getitem__)
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
            formula.signed_formula(VERSION, self.signers, self.served(changed, signature).__getitem__)

    def test_refuses_another_namespace(self) -> None:
        manifest = manifest_for(VERSION, SUMS)
        signature = self.sign(manifest, namespace="git")
        with self.assertRaisesRegex(formula.FormulaError, "does not verify"):
            formula.signed_formula(VERSION, self.signers, self.served(manifest, signature).__getitem__)

    def test_refuses_an_unlisted_key(self) -> None:
        manifest = manifest_for(VERSION, SUMS)
        signature = self.sign(manifest)
        self.signers.write_text("")
        with self.assertRaisesRegex(formula.FormulaError, "does not verify"):
            formula.signed_formula(VERSION, self.signers, self.served(manifest, signature).__getitem__)

    def test_refuses_a_bad_version(self) -> None:
        with self.assertRaisesRegex(formula.FormulaError, "not a release version"):
            formula.signed_formula("1.2.3/../x", self.signers, {}.__getitem__)


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


class FormulaVersionTest(unittest.TestCase):
    def test_no_url(self) -> None:
        with self.assertRaisesRegex(formula.FormulaError, "no warden release URL"):
            formula.formula_version('url "https://example.com/warden-1.2.3.tar.gz"')


if __name__ == "__main__":
    unittest.main()
