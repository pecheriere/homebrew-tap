"""Tests for landfall.py's check-tree, fetch and command line, with throwaway git
repositories and no network: the formula's own verification is stubbed here,
and tested in test_landfall.py.

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

# Commits in the throwaway repositories carry a made-up author, and git reads
# no user configuration, so nothing signs them.
GIT = {
    **landfall.GIT_ENV,
    "GIT_AUTHOR_NAME": "Test",
    "GIT_AUTHOR_EMAIL": "test@example.com",
    "GIT_COMMITTER_NAME": "Test",
    "GIT_COMMITTER_EMAIL": "test@example.com",
}


def formula(version: str) -> bytes:
    return f'class Landfall < Formula\n  version "{version}"\nend\n'.encode()


class Checked:
    """A stand-in for check that records its arguments and passes."""

    def __init__(self) -> None:
        self.calls: list[tuple[bytes, bytes | None, str | None]] = []

    def __call__(self, text: bytes, base: bytes | None, floor: str | None) -> str:
        self.calls.append((text, base, floor))
        return landfall.formula_version(text.decode())


class Repo:
    """A throwaway git repository to commit files in."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.git("init", "-q", str(path))

    def git(self, *args: str) -> str:
        return subprocess.run(["git", *args], env=GIT, check=True, capture_output=True, text=True).stdout

    def commit(self, files: dict[str, bytes | None], links: dict[str, str] | None = None) -> str:
        for name, data in files.items():
            path = self.path / name
            if data is None:
                self.git("-C", str(self.path), "rm", "-q", "-r", name)
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            self.git("-C", str(self.path), "add", name)
        for name, target in (links or {}).items():
            (self.path / name).parent.mkdir(parents=True, exist_ok=True)
            (self.path / name).symlink_to(target)
            self.git("-C", str(self.path), "add", name)
        self.git("-C", str(self.path), "commit", "-q", "--allow-empty", "-m", "change")
        return self.git("-C", str(self.path), "rev-parse", "HEAD").strip()


class TempDirTest(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)


class StrayFormulasTest(unittest.TestCase):
    def test_finds_every_other_landfall_formula(self) -> None:
        stray = [
            "Formula/Landfall.rb",
            "Formula/l/landfall.rb",
            "Formula/l/LANDFALL_x.rb",
            "Formula/landfall-pro.rb",
            "HomebrewFormula/landfall.rb",
            "Landfall.RB",
            "docs/landfall.rb",
            "elsewhere/landfall.rb",
        ]
        paths = [landfall.FORMULA, "Formula/warden.rb", "scripts/landfall.py", "elsewhere/landfall.rb/inside", *stray]
        self.assertEqual(landfall.stray_formulas(paths), sorted(stray))

    def test_this_repository_has_none(self) -> None:
        root = Path(__file__).resolve().parent.parent
        tracked = subprocess.run(["git", "-C", str(root), "ls-files"], capture_output=True, text=True, check=True)
        self.assertEqual(landfall.stray_formulas(tracked.stdout.splitlines()), [])


class JudgeTreeTest(unittest.TestCase):
    def test_refuses_to_delete_the_formula(self) -> None:
        with self.assertRaisesRegex(landfall.LandfallError, "deletes Formula/landfall.rb, which the base has"):
            landfall.judge_tree(None, formula("1.2.3"), "1.2.3", Checked())

    def test_no_formula_on_either_side(self) -> None:
        checked = Checked()
        self.assertIn("nothing to check", landfall.judge_tree(None, None, "1.2.3", checked))
        self.assertEqual(checked.calls, [])

    def test_checks_the_formula_with_base_and_floor(self) -> None:
        checked = Checked()
        message = landfall.judge_tree(formula("1.3.0"), formula("1.2.3"), "1.2.3", checked)
        self.assertEqual(message, "Formula/landfall.rb is landfall 1.3.0's verified formula")
        self.assertEqual(checked.calls, [(formula("1.3.0"), formula("1.2.3"), "1.2.3")])


class CheckTreeTest(TempDirTest):
    """A base repository whose formula went 1.0.0, 1.2.0, then was deleted."""

    def setUp(self) -> None:
        super().setUp()
        self.base = Repo(self.dir / "base")
        for change in (formula("1.0.0"), formula("1.2.0"), None):
            self.base.commit({landfall.FORMULA: change})
        self.change = Repo(self.dir / "change")

    def check_tree(self, base_revision: str, checked: Checked | None = None) -> str:
        return landfall.check_tree(self.change.path, "HEAD", self.base.path, base_revision, checked or Checked())

    def test_history_and_floor(self) -> None:
        self.assertEqual(landfall.history(self.base.path, "HEAD"), ["1.2.0", "1.0.0"])
        self.assertEqual(landfall.formula_at(self.base.path, "HEAD~1"), formula("1.2.0"))
        self.assertIsNone(landfall.formula_at(self.base.path, "HEAD"))

    def test_refuses_to_come_back_below_the_floor_after_a_deletion(self) -> None:
        self.change.commit({landfall.FORMULA: formula("1.1.0")})
        with self.assertRaisesRegex(landfall.LandfallError, "already been at 1.2.0"):
            landfall.check_tree(self.change.path, "HEAD", self.base.path, "HEAD")

    def test_passes_the_committed_formula_base_and_floor_to_check(self) -> None:
        self.change.commit({landfall.FORMULA: formula("1.3.0")})
        (self.change.path / landfall.FORMULA).write_bytes(formula("9.9.9"))
        checked = Checked()
        self.check_tree("HEAD~1", checked)
        self.assertEqual(checked.calls, [(formula("1.3.0"), formula("1.2.0"), "1.2.0")])

    def test_refuses_a_deletion(self) -> None:
        self.change.commit({"README.md": b"readme\n"})
        with self.assertRaisesRegex(landfall.LandfallError, "deletes"):
            self.check_tree("HEAD~1")

    def test_no_formula_anywhere(self) -> None:
        self.change.commit({"README.md": b"readme\n"})
        self.assertIn("nothing to check", self.check_tree("HEAD"))

    def test_refuses_a_stray_formula(self) -> None:
        self.change.commit({landfall.FORMULA: formula("1.3.0"), "Formula/l/landfall.rb": formula("9.0.0")})
        with self.assertRaisesRegex(landfall.LandfallError, "also has Formula/l/landfall.rb"):
            self.check_tree("HEAD~1")

    def test_refuses_a_formula_that_is_a_symbolic_link(self) -> None:
        self.change.commit({"elsewhere.rb": formula("1.3.0")}, links={landfall.FORMULA: "../elsewhere.rb"})
        with self.assertRaisesRegex(landfall.LandfallError, "not a regular file"):
            self.check_tree("HEAD~1")

    def test_refuses_formula_as_a_symbolic_link(self) -> None:
        self.change.commit({"elsewhere/other.rb": formula("1.3.0")}, links={"Formula": "elsewhere"})
        with self.assertRaisesRegex(landfall.LandfallError, "Formula is not a directory"):
            self.check_tree("HEAD~1")

    def test_refuses_a_shallow_clone(self) -> None:
        shallow = self.dir / "shallow"
        self.base.git("clone", "-q", "--depth", "1", self.base.path.as_uri(), str(shallow))
        self.change.commit({"README.md": b"readme\n"})
        with self.assertRaisesRegex(landfall.LandfallError, "shallow clone"):
            landfall.check_tree(self.change.path, "HEAD", shallow, "HEAD", Checked())

    def test_refuses_an_unknown_revision(self) -> None:
        self.change.commit({"README.md": b"readme\n"})
        with self.assertRaisesRegex(landfall.LandfallError, "git rev-parse failed"):
            self.check_tree("HEAD~5")


class Verified:
    """A stand-in for verified_formula that serves fixed formulae."""

    def __init__(self, *versions: str) -> None:
        self.served = {version: formula(version) for version in versions}
        self.calls: list[tuple[str, ...]] = []

    def __call__(self, version: str, *rest: object) -> bytes:
        self.calls.append((version, *map(str, rest)))
        return self.served[version]


class FetchFormulaTest(TempDirTest):
    def test_writes_a_new_formula(self) -> None:
        out = self.dir / "landfall.rb"
        landfall.fetch_formula("1.2.3", out, verified=Verified("1.2.3"))
        self.assertEqual(out.read_bytes(), formula("1.2.3"))

    def test_writes_nothing_when_verification_fails(self) -> None:
        out = self.dir / "landfall.rb"

        def refuse(version: str) -> bytes:
            raise landfall.LandfallError("no")

        with self.assertRaisesRegex(landfall.LandfallError, "no"):
            landfall.fetch_formula("1.2.3", out, verified=refuse)
        self.assertFalse(out.exists())

    def test_refuses_to_go_back_from_the_file_there(self) -> None:
        out = self.dir / "landfall.rb"
        out.write_bytes(formula("1.10.0"))
        verified = Verified("1.2.3")
        with self.assertRaisesRegex(landfall.LandfallError, "from landfall 1.10.0 to 1.2.3"):
            landfall.fetch_formula("1.2.3", out, verified=verified)
        self.assertEqual(verified.calls, [])
        self.assertEqual(out.read_bytes(), formula("1.10.0"))

    def test_leaves_the_same_formula_alone(self) -> None:
        out = self.dir / "landfall.rb"
        out.write_bytes(formula("1.2.3"))
        self.assertIn("already", landfall.fetch_formula("1.2.3", out, verified=Verified("1.2.3")))

    def test_refuses_another_formula_of_the_same_version(self) -> None:
        out = self.dir / "landfall.rb"
        out.write_bytes(formula("1.2.3") + b"\n")
        with self.assertRaisesRegex(landfall.LandfallError, "from landfall 1.2.3 to 1.2.3"):
            landfall.fetch_formula("1.2.3", out, verified=Verified("1.2.3"))

    def test_refuses_to_go_below_the_floor_of_the_repository(self) -> None:
        repo = Repo(self.dir / "tap")
        repo.commit({"Formula/warden.rb": b"warden\n", landfall.FORMULA: formula("1.4.0")})
        repo.commit({landfall.FORMULA: None})
        with self.assertRaisesRegex(landfall.LandfallError, "from landfall 1.4.0 to 1.3.0"):
            landfall.fetch_formula("1.3.0", repo.path / landfall.FORMULA, verified=Verified("1.3.0"))
        landfall.fetch_formula("1.4.0", repo.path / landfall.FORMULA, verified=Verified("1.4.0"))
        self.assertEqual((repo.path / landfall.FORMULA).read_bytes(), formula("1.4.0"))

    def test_finds_the_floor_when_formula_is_gone(self) -> None:
        repo = Repo(self.dir / "tap")
        repo.commit({landfall.FORMULA: formula("1.4.0")})
        repo.commit({landfall.FORMULA: None})
        self.assertFalse((repo.path / "Formula").exists())
        with self.assertRaisesRegex(landfall.LandfallError, "from landfall 1.4.0 to 1.3.0"):
            landfall.fetch_formula("1.3.0", repo.path / landfall.FORMULA, verified=Verified("1.3.0"))

    def test_refuses_a_prerelease_without_the_flag(self) -> None:
        with self.assertRaisesRegex(landfall.LandfallError, "pre-release"):
            landfall.fetch_formula("1.2.3-rc.1", self.dir / "landfall.rb", verified=Verified())

    def test_allow_prerelease_writes_a_new_file_outside_a_repository(self) -> None:
        out = self.dir / "landfall.rb"
        verified = Verified("1.2.3-rc.1")
        landfall.fetch_formula("1.2.3-rc.1", out, True, verified)
        self.assertEqual(verified.calls, [("1.2.3-rc.1", "True")])
        self.assertEqual(out.read_bytes(), formula("1.2.3-rc.1"))

    def test_allow_prerelease_refuses_an_existing_file_or_a_repository(self) -> None:
        existing = self.dir / "landfall.rb"
        existing.write_bytes(b"x")
        repo = Repo(self.dir / "tap")
        for out in (existing, repo.path / landfall.FORMULA):
            with self.subTest(out=out), self.assertRaisesRegex(landfall.LandfallError, "outside any git repository"):
                landfall.fetch_formula("1.2.3-rc.1", out, True, Verified("1.2.3-rc.1"))


class MainTest(TempDirTest):
    def main(self, *argv: str) -> int:
        with mock.patch("sys.stdout"), mock.patch("sys.stderr"):
            return landfall.main(list(argv))

    def test_fetch_writes_the_verified_formula(self) -> None:
        out = self.dir / "landfall.rb"
        with mock.patch.object(landfall, "verified_formula", Verified("1.2.3")):
            self.assertEqual(self.main("fetch", "1.2.3", str(out)), 0)
        self.assertEqual(out.read_bytes(), formula("1.2.3"))

    def test_fetch_writes_nothing_when_verification_fails(self) -> None:
        out = self.dir / "landfall.rb"
        with mock.patch.object(landfall, "verified_formula", side_effect=landfall.LandfallError("no")):
            self.assertEqual(self.main("fetch", "1.2.3", str(out)), 1)
        self.assertFalse(out.exists())

    def test_fetch_passes_allow_prerelease(self) -> None:
        out = self.dir / "landfall.rb"
        verified = Verified("1.2.3-rc.1")
        with mock.patch.object(landfall, "verified_formula", verified):
            self.assertEqual(self.main("fetch", "--allow-prerelease", "1.2.3-rc.1", str(out)), 0)
        self.assertEqual(verified.calls, [("1.2.3-rc.1", "True")])

    def test_usage(self) -> None:
        for argv in (
            ["fetch", "1.2.3"],
            ["check"],
            ["check", "--base", "", "landfall.rb"],
            ["check-tree", "change", "HEAD", "base"],
            ["check-tree", "--allow-prerelease", "change", "HEAD", "base", "HEAD"],
        ):
            with self.subTest(argv=argv), mock.patch.object(landfall, "verified_formula") as verified:
                self.assertEqual(self.main(*argv), 2)
                verified.assert_not_called()


if __name__ == "__main__":
    unittest.main()
