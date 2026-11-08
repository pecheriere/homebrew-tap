"""Tests for scope.py, in a throwaway repository with a throwaway key.

Run: python3 -I -m unittest discover -s scripts -p 'test_*.py'
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import scope

EMAIL = "maintainer@example.com"


class ScopeTest(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        self.key = self.dir / "key"
        subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(self.key)], check=True)
        public = (self.dir / "key.pub").read_text().split()
        self.signers = self.dir / "signers"
        self.signers.write_text(f'{EMAIL} namespaces="git" {public[0]} {public[1]}\n')
        self.repo = self.dir / "repo"
        self.repo.mkdir()
        self.env = {
            "PATH": os.environ["PATH"],
            "HOME": str(self.dir),
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_AUTHOR_NAME": "Maintainer",
            "GIT_AUTHOR_EMAIL": EMAIL,
            "GIT_COMMITTER_NAME": "Maintainer",
            "GIT_COMMITTER_EMAIL": EMAIL,
        }
        self.git("init", "-q", "-b", "main")
        self.write("Formula/warden.rb", "v1\n")
        self.write("README.md", "tap\n")
        self.base = self.commit("base", signed=True)

    def git(self, *args: str) -> str:
        result = subprocess.run(
            ["git", "-C", str(self.repo), *args], env=self.env, capture_output=True, text=True, check=True
        )
        return result.stdout.strip()

    def write(self, path: str, text: str) -> None:
        target = self.repo / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)

    def commit(self, message: str, signed: bool) -> str:
        self.git("add", "-A")
        sign = ["-c", "gpg.format=ssh", "-c", f"user.signingkey={self.key}", "commit", "-S"] if signed else ["commit"]
        self.git(*sign, "-q", "-m", message)
        return self.git("rev-parse", "HEAD")

    def decide(self, head: str) -> str:
        return scope.decide(self.repo, self.base, head, self.signers)

    def test_unsigned_formula_bump_passes(self) -> None:
        self.write("Formula/warden.rb", "v2\n")
        self.assertIn("only a formula bump", self.decide(self.commit("bump", signed=False)))

    def test_unsigned_change_to_anything_else_fails(self) -> None:
        self.write("Formula/warden.rb", "v2\n")
        self.write("README.md", "changed\n")
        with self.assertRaisesRegex(scope.ScopeError, "must be signed"):
            self.decide(self.commit("bump and more", signed=False))

    def test_unsigned_shadow_formula_fails(self) -> None:
        self.write("Formula/x/warden.rb", "evil\n")
        with self.assertRaisesRegex(scope.ScopeError, "must be signed"):
            self.decide(self.commit("shadow", signed=False))

    def test_unsigned_deletion_fails(self) -> None:
        (self.repo / "Formula/warden.rb").unlink()
        with self.assertRaisesRegex(scope.ScopeError, "must be signed"):
            self.decide(self.commit("delete", signed=False))

    def test_unsigned_symlink_formula_fails(self) -> None:
        (self.repo / "Formula/warden.rb").unlink()
        (self.repo / "Formula/warden.rb").symlink_to("../README.md")
        with self.assertRaisesRegex(scope.ScopeError, "must be signed"):
            self.decide(self.commit("symlink", signed=False))

    def test_unsigned_formula_not_in_the_list_fails(self) -> None:
        self.write("Formula/other.rb", "v1\n")
        self.commit("add other", signed=True)
        self.base = self.git("rev-parse", "HEAD")
        self.write("Formula/other.rb", "v2\n")
        with self.assertRaisesRegex(scope.ScopeError, "must be signed"):
            self.decide(self.commit("bump other", signed=False))

    def test_signed_change_to_anything_passes(self) -> None:
        self.write("scripts/formula.py", "print()\n")
        self.write("Formula/x/warden.rb", "new\n")
        self.assertIn("signed by the maintainer", self.decide(self.commit("rework", signed=True)))

    def test_one_unsigned_commit_among_signed_ones_fails(self) -> None:
        self.write("README.md", "one\n")
        self.commit("signed", signed=True)
        self.write("README.md", "two\n")
        unsigned = self.commit("unsigned", signed=False)
        with self.assertRaisesRegex(scope.ScopeError, unsigned):
            self.decide(unsigned)

    def test_another_key_fails(self) -> None:
        self.signers.write_text("")
        self.write("README.md", "changed\n")
        with self.assertRaisesRegex(scope.ScopeError, "must be signed"):
            self.decide(self.commit("signed by an unlisted key", signed=True))

    def test_no_change_fails(self) -> None:
        with self.assertRaisesRegex(scope.ScopeError, "no commits"):
            self.decide(self.base)


if __name__ == "__main__":
    unittest.main()
