"""Tests for landfall.py, with a throwaway key and no network.

The tag and the asset are served from memory, and the attestation check and
GitHub's pre-release flag are stubs: gh needs the network and a real release,
so only CI's check of a committed formula runs them. testdata/v0.1.0-rc.1 holds
landfall 0.1.0-rc.1's real tag object and landfall.rb asset (as asset), which check the
key in landfall-release-signers and the refusal of release candidates.

Run: python3 -I -m unittest discover -s scripts -p 'test_*.py'
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import landfall

VERSION = "1.2.3"
RC = Path(__file__).resolve().parent / "testdata" / "v0.1.0-rc.1"
COMMIT = "0123456789abcdef0123456789abcdef01234567"
FORMULA = f"""\
class Landfall < Formula
  desc "Continuous delivery for self-hosters"
  version "{VERSION}"
end
""".encode()


def tag_payload(commit: str = COMMIT, kind: str = "commit", name: str = f"v{VERSION}") -> bytes:
    return (
        f"object {commit}\ntype {kind}\ntag {name}\n"
        f"tagger Someone <someone@example.com> 1700000000 +0000\n\n{name}\n"
    ).encode()


class VerifiedFormulaTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.key = self.dir / "key"
        subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(self.key)], check=True)
        public = (self.dir / "key.pub").read_text().split()
        self.signers = self.dir / "signers"
        self.signers.write_text(f'{landfall.IDENTITY} namespaces="{landfall.NAMESPACE}" {public[0]} {public[1]}\n')
        self.attested: list[tuple[bytes, str, str]] = []

    def sign(self, payload: bytes, namespace: str = landfall.NAMESPACE) -> bytes:
        path = self.dir / "payload"
        path.write_bytes(payload)
        subprocess.run(["ssh-keygen", "-q", "-Y", "sign", "-n", namespace, "-f", str(self.key), str(path)], check=True)
        return (self.dir / "payload.sig").read_bytes()

    def signed_tag(self, payload: bytes | None = None, namespace: str = landfall.NAMESPACE) -> bytes:
        payload = tag_payload() if payload is None else payload
        return payload + self.sign(payload, namespace)

    def attest(self, path: Path, version: str, commit: str) -> None:
        self.attested.append((path.read_bytes(), version, commit))

    def verified(self, raw_tag: bytes, asset: bytes = FORMULA, version: str = VERSION) -> bytes:
        return landfall.verified_formula(
            version,
            signers=self.signers,
            prerelease=lambda version: False,
            get={VERSION: asset}.__getitem__,
            get_tag={VERSION: raw_tag}.__getitem__,
            attest_file=self.attest,
        )

    def test_a_good_tag_passes(self) -> None:
        self.assertEqual(self.verified(self.signed_tag()), FORMULA)
        self.assertEqual(self.attested, [(FORMULA, VERSION, COMMIT)])

    def test_refuses_a_changed_payload(self) -> None:
        signature = self.sign(tag_payload())
        changed = tag_payload(commit="f" * 40)
        with self.assertRaisesRegex(landfall.LandfallError, "does not verify"):
            self.verified(changed + signature)
        self.assertEqual(self.attested, [])

    def test_refuses_another_namespace(self) -> None:
        with self.assertRaisesRegex(landfall.LandfallError, "does not verify"):
            self.verified(self.signed_tag(namespace="file"))

    def test_refuses_an_unlisted_key(self) -> None:
        raw = self.signed_tag()
        self.signers.write_text("")
        with self.assertRaisesRegex(landfall.LandfallError, "does not verify"):
            self.verified(raw)

    def test_refuses_another_tag_name(self) -> None:
        with self.assertRaisesRegex(landfall.LandfallError, "is named 'tag v1.2.4'"):
            self.verified(self.signed_tag(tag_payload(name="v1.2.4")))

    def test_refuses_an_object_that_is_not_a_commit(self) -> None:
        with self.assertRaisesRegex(landfall.LandfallError, "does not name a commit"):
            self.verified(self.signed_tag(tag_payload(kind="tree")))

    def test_refuses_a_missing_commit(self) -> None:
        with self.assertRaisesRegex(landfall.LandfallError, "names no object"):
            self.verified(self.signed_tag(tag_payload(commit="")))

    def test_refuses_an_extra_signature(self) -> None:
        raw = self.signed_tag()
        with self.assertRaisesRegex(landfall.LandfallError, "exactly one signature"):
            self.verified(raw + raw[raw.index(landfall.BEGIN) :])

    def test_refuses_an_unsigned_tag(self) -> None:
        with self.assertRaisesRegex(landfall.LandfallError, "exactly one signature"):
            self.verified(tag_payload())

    def test_refuses_a_garbled_signature(self) -> None:
        raw = self.signed_tag()
        garbled = raw.replace(landfall.BEGIN, landfall.BEGIN + b"AAAA")
        with self.assertRaisesRegex(landfall.LandfallError, "does not verify"):
            self.verified(garbled)

    def test_refuses_text_after_the_signature(self) -> None:
        with self.assertRaisesRegex(landfall.LandfallError, "does not end with an SSH signature"):
            self.verified(self.signed_tag() + b"more\n")

    def test_refuses_an_extra_header(self) -> None:
        payload = tag_payload().replace(b"\n\n", b"\nencoding ISO-8859-1\n\n", 1)
        with self.assertRaisesRegex(landfall.LandfallError, "unexpected header"):
            self.verified(self.signed_tag(payload))

    def test_refuses_an_asset_for_another_version(self) -> None:
        other = FORMULA.replace(VERSION.encode(), b"1.2.2")
        with self.assertRaisesRegex(landfall.LandfallError, "declares version 1.2.2"):
            self.verified(self.signed_tag(), asset=other)

    def test_refuses_when_the_attestation_fails(self) -> None:
        def refuse(path: Path, version: str, commit: str) -> None:
            raise landfall.LandfallError("no attestation")

        with self.assertRaisesRegex(landfall.LandfallError, "no attestation"):
            landfall.verified_formula(
                VERSION,
                signers=self.signers,
                prerelease=lambda version: False,
                get={VERSION: FORMULA}.__getitem__,
                get_tag={VERSION: self.signed_tag()}.__getitem__,
                attest_file=refuse,
            )

    def test_refuses_a_bad_version(self) -> None:
        for version in ("1.2.3/../x", "1.2", "v1.2.3", "1.2.3-", "1.2.3-rc..1", "1.2.3 ", "١.2.3"):
            with self.subTest(version=version), self.assertRaisesRegex(landfall.LandfallError, "not a release"):
                landfall.verified_formula(version, True, self.signers, get_tag={}.__getitem__)

    def test_refuses_a_prerelease_version(self) -> None:
        with self.assertRaisesRegex(landfall.LandfallError, "1.2.3-rc.1 is a pre-release"):
            landfall.verified_formula("1.2.3-rc.1", signers=self.signers, get_tag={}.__getitem__)

    def test_refuses_a_release_github_marks_as_prerelease(self) -> None:
        with self.assertRaisesRegex(landfall.LandfallError, "GitHub marks v1.2.3 as a pre-release"):
            landfall.verified_formula(VERSION, signers=self.signers, prerelease=lambda v: True, get_tag={}.__getitem__)

    def test_allow_prerelease_lifts_both_refusals(self) -> None:
        rc = FORMULA.replace(VERSION.encode(), b"1.2.3-rc.1")
        raw = self.signed_tag(tag_payload(name="v1.2.3-rc.1"))
        asset = landfall.verified_formula(
            "1.2.3-rc.1",
            True,
            self.signers,
            prerelease=lambda v: True,
            get={"1.2.3-rc.1": rc}.__getitem__,
            get_tag={"1.2.3-rc.1": raw}.__getitem__,
            attest_file=self.attest,
        )
        self.assertEqual(asset, rc)


class ReleaseCandidateTest(unittest.TestCase):
    """landfall 0.1.0-rc.1's real tag and asset, against this repository's key."""

    asset = (RC / "asset").read_bytes()
    raw_tag = (RC / "tag").read_bytes()

    def test_the_real_tag_verifies_against_the_key(self) -> None:
        attested: list[str] = []
        asset = landfall.verified_formula(
            "0.1.0-rc.1",
            allow_prerelease=True,
            get={"0.1.0-rc.1": self.asset}.__getitem__,
            get_tag={"0.1.0-rc.1": self.raw_tag}.__getitem__,
            attest_file=lambda path, version, commit: attested.append(commit),
        )
        self.assertEqual(asset, self.asset)
        self.assertEqual(attested, ["42e8a3c14edc7a869fe6a45e9d1712a5e59bfea5"])

    def test_check_refuses_the_release_candidate(self) -> None:
        with self.assertRaisesRegex(landfall.LandfallError, "0.1.0-rc.1 is a pre-release"):
            landfall.check(self.asset, verified={}.__getitem__)

    def test_check_takes_no_allow_prerelease(self) -> None:
        with mock.patch("sys.stderr"):
            self.assertEqual(landfall.main(["check", "--allow-prerelease", "Formula/landfall.rb"]), 2)


def formula(version: str) -> bytes:
    return FORMULA.replace(VERSION.encode(), version.encode())


class CheckTest(unittest.TestCase):
    def test_accepts_the_verified_asset(self) -> None:
        self.assertEqual(landfall.check(FORMULA, verified={VERSION: FORMULA}.__getitem__), VERSION)

    def test_accepts_a_newer_version_than_the_base(self) -> None:
        for base in ("1.2.2", "1.1.9", "0.10.0"):
            with self.subTest(base=base):
                verified = {VERSION: FORMULA}.__getitem__
                self.assertEqual(landfall.check(FORMULA, formula(base), verified=verified), VERSION)

    def test_accepts_the_base_formula_unchanged(self) -> None:
        self.assertEqual(landfall.check(FORMULA, FORMULA, verified={VERSION: FORMULA}.__getitem__), VERSION)

    def test_refuses_an_older_version_than_the_base(self) -> None:
        for base in ("1.10.0", "1.2.10", "2.0.0"):
            with self.subTest(base=base), self.assertRaisesRegex(landfall.LandfallError, f"from landfall {base} to"):
                landfall.check(FORMULA, formula(base), verified={}.__getitem__)

    def test_refuses_another_formula_of_the_same_version(self) -> None:
        with self.assertRaisesRegex(landfall.LandfallError, "from landfall 1.2.3 to 1.2.3"):
            landfall.check(FORMULA, FORMULA + b"\n", verified={}.__getitem__)

    def test_refuses_a_base_it_cannot_read(self) -> None:
        for base, message in ((formula("1.2.2-rc.1"), "pre-release"), (b"nothing", "exactly one version")):
            with self.subTest(base=base), self.assertRaisesRegex(landfall.LandfallError, message):
                landfall.check(FORMULA, base, verified={}.__getitem__)

    def test_accepts_a_version_at_or_above_the_floor(self) -> None:
        for floor in ("1.2.3", "1.2.2", "0.99.0"):
            with self.subTest(floor=floor):
                self.assertEqual(landfall.check(FORMULA, None, floor, {VERSION: FORMULA}.__getitem__), VERSION)

    def test_refuses_a_version_below_the_floor(self) -> None:
        for floor in ("1.2.4", "1.10.0", "2.0.0"):
            with self.subTest(floor=floor), self.assertRaisesRegex(landfall.LandfallError, f"already been at {floor}"):
                landfall.check(FORMULA, None, floor, {}.__getitem__)

    def test_refuses_a_version_newer_than_the_base_but_below_the_floor(self) -> None:
        with self.assertRaisesRegex(landfall.LandfallError, "already been at 1.3.0"):
            landfall.check(FORMULA, formula("1.0.0"), "1.3.0", {}.__getitem__)

    def test_the_base_unchanged_passes_whatever_the_floor(self) -> None:
        self.assertEqual(landfall.check(FORMULA, FORMULA, "9.0.0", {VERSION: FORMULA}.__getitem__), VERSION)

    def test_highest(self) -> None:
        self.assertEqual(landfall.highest(["1.2.3", "1.10.0", "1.9.9"]), "1.10.0")
        self.assertEqual(landfall.highest(["0.1.0-rc.1", "0.0.9"]), "0.0.9")
        self.assertIsNone(landfall.highest([]))
        self.assertIsNone(landfall.highest(["0.1.0-rc.1"]))

    def test_refuses_a_formula_one_byte_off(self) -> None:
        changed = FORMULA.replace(b"self-hosters", b"self-hostert")
        with self.assertRaisesRegex(landfall.LandfallError, "not v1.2.3's verified"):
            landfall.check(changed, verified={VERSION: FORMULA}.__getitem__)

    def test_refuses_a_formula_without_a_version(self) -> None:
        with self.assertRaisesRegex(landfall.LandfallError, "exactly one version"):
            landfall.check(b"class Landfall < Formula\nend\n", verified={}.__getitem__)

    def test_refuses_a_formula_with_a_bad_version(self) -> None:
        with self.assertRaisesRegex(landfall.LandfallError, "not a release version"):
            landfall.check(formula("1.2.3/../x"), verified={}.__getitem__)


class AttestationTest(unittest.TestCase):
    def test_command(self) -> None:
        self.assertEqual(
            landfall.attestation_command(Path("landfall.rb"), VERSION, COMMIT),
            [
                "gh",
                "attestation",
                "verify",
                "landfall.rb",
                "--hostname=github.com",
                "--repo=pecheriere/landfall",
                "--signer-workflow=pecheriere/landfall/.github/workflows/release.yml",
                f"--source-ref=refs/tags/v{VERSION}",
                f"--source-digest={COMMIT}",
                "--deny-self-hosted-runners",
            ],
        )

    def test_refuses_an_empty_commit(self) -> None:
        with self.assertRaisesRegex(landfall.LandfallError, "not a commit"):
            landfall.attestation_command(Path("landfall.rb"), VERSION, "")

    def test_refuses_without_gh_for_the_attestation(self) -> None:
        with (
            mock.patch.object(landfall.shutil, "which", return_value=None),
            self.assertRaisesRegex(landfall.LandfallError, "gh is not installed"),
        ):
            landfall.attest(Path("landfall.rb"), VERSION, COMMIT)


class ProcessTest(unittest.TestCase):
    """The helpers that call git and gh, with run replaced."""

    def prerelease_flag(self, out: bytes) -> bool:
        with (
            mock.patch.object(landfall.shutil, "which", return_value="gh"),
            mock.patch.object(landfall, "run", return_value=out),
        ):
            return landfall.is_prerelease(VERSION)

    def test_is_prerelease_reads_the_flag(self) -> None:
        self.assertTrue(self.prerelease_flag(b'{"prerelease": true}'))
        self.assertFalse(self.prerelease_flag(b'{"prerelease": false}'))

    def test_is_prerelease_refuses_a_missing_or_strange_flag(self) -> None:
        for out in (b"{}", b'{"prerelease": null}', b'{"prerelease": "false"}', b"not json", b"[]"):
            with self.subTest(out=out), self.assertRaisesRegex(landfall.LandfallError, "pre-release flag"):
                self.prerelease_flag(out)

    def test_is_prerelease_refuses_without_gh(self) -> None:
        with (
            mock.patch.object(landfall.shutil, "which", return_value=None),
            self.assertRaisesRegex(landfall.LandfallError, "gh is not installed"),
        ):
            landfall.is_prerelease(VERSION)

    def test_raw_tag_refuses_a_lightweight_tag(self) -> None:
        def run(args: list[str], what: str, env: dict[str, str] | None = None) -> bytes:
            self.assertIs(env, landfall.GIT_ENV)
            return b"commit\n" if args[-2:] == ["-t", f"refs/tags/v{VERSION}"] else b""

        with (
            mock.patch.object(landfall, "run", run),
            self.assertRaisesRegex(landfall.LandfallError, "not an annotated tag"),
        ):
            landfall.raw_tag(VERSION)

    def test_git_env_drops_every_inherited_git_variable(self) -> None:
        env = landfall.git_env(
            {
                "PATH": "/usr/bin",
                "HOME": "/home/someone",
                "GIT_CONFIG_COUNT": "1",
                "GIT_CONFIG_KEY_0": "url.https://mirror.example/.insteadOf",
                "GIT_CONFIG_VALUE_0": "https://github.com/",
                "GIT_CONFIG_PARAMETERS": "'http.sslverify'='false'",
                "GIT_DIR": "/elsewhere",
                "GIT_SSL_NO_VERIFY": "1",
                "GIT_CONFIG_GLOBAL": "/home/someone/.gitconfig",
            }
        )
        self.assertEqual(
            env,
            {
                "PATH": "/usr/bin",
                "HOME": "/home/someone",
                "GIT_CONFIG_GLOBAL": landfall.os.devnull,
                "GIT_CONFIG_NOSYSTEM": "1",
                "GIT_TERMINAL_PROMPT": "0",
            },
        )


if __name__ == "__main__":
    unittest.main()
