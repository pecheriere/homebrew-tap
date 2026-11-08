"""Decides whether a pull request may merge on the formula checks alone.

Usage:
  python3 -I scripts/scope.py <repository> <base-commit> <head-commit>

A bump that only modifies a formula in FORMULAE, as a regular file, is covered
by the manifest check and passes here. Any other change, such as another file,
a new, deleted or renamed file, a symbolic link or a second formula elsewhere
under Formula/, passes only if every commit in the pull request carries a good
SSH signature from a key in maintainer-signers, the maintainer's commit keys.
Commits that warden's workflow makes through the API carry GitHub's signature
instead, so the workflow's token can bump a formula and do nothing else.

CI runs this script, and maintainer-signers, as they are on the pull request's
base, so a pull request cannot change the rules it is judged by. It reads the
pull request's commits as data, with git; it needs nothing outside the standard
library.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

# The formulae warden's and other projects' workflows may bump on their own.
FORMULAE = ("warden", "landfall")
MAINTAINER_SIGNERS = Path(__file__).resolve().parent.parent / "maintainer-signers"
REGULAR_FILE = "100644"


class ScopeError(Exception):
    pass


def git(repo: Path, *args: str) -> bytes:
    result = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, check=False)
    if result.returncode != 0:
        raise ScopeError(f"git {args[0]} failed: {result.stderr.decode(errors='replace').strip()}")
    return result.stdout


def changes(repo: Path, base: str, head: str) -> list[tuple[str, str]]:
    """(status, path) for each change from base to head, with renames as two."""
    out = git(repo, "diff", "--no-renames", "--name-status", "-z", base, head, "--")
    fields = out.decode("utf-8", errors="surrogateescape").split("\0")
    if fields and fields[-1] == "":
        fields.pop()
    if len(fields) % 2:
        raise ScopeError("git diff printed an unexpected list of changes")
    return list(zip(fields[0::2], fields[1::2], strict=True))


def mode(repo: Path, commit: str, path: str) -> str:
    out = git(repo, "ls-tree", "-z", commit, "--", path).decode("utf-8", errors="surrogateescape")
    entry = out.split("\0")[0]
    return entry.split(" ", 1)[0] if entry else ""


def formula_bump_only(repo: Path, base: str, head: str) -> bool:
    found = changes(repo, base, head)
    allowed = {f"Formula/{name}.rb" for name in FORMULAE}
    return bool(found) and all(
        status == "M" and path in allowed and mode(repo, head, path) == REGULAR_FILE for status, path in found
    )


def unsigned_commits(repo: Path, base: str, head: str, signers: Path) -> list[str]:
    commits = git(repo, "rev-list", f"{base}..{head}").decode().split()
    if not commits:
        raise ScopeError("the pull request has no commits")
    bad = []
    for commit in commits:
        result = subprocess.run(
            ["git", "-C", str(repo), "-c", f"gpg.ssh.allowedSignersFile={signers}", "verify-commit", commit],
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            bad.append(commit)
    return bad


def decide(repo: Path, base: str, head: str, signers: Path = MAINTAINER_SIGNERS) -> str:
    if formula_bump_only(repo, base, head):
        return "only a formula bump: the manifest check covers it"
    bad = unsigned_commits(repo, base, head, signers)
    if bad:
        raise ScopeError(
            "this changes more than a formula, so every commit must be signed by a key in "
            f"maintainer-signers; these are not: {' '.join(bad)}"
        )
    return "more than a formula bump, and every commit is signed by the maintainer"


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(__doc__.split("\n\n")[1], file=sys.stderr)
        return 2
    try:
        print(decide(Path(argv[0]), argv[1], argv[2]))
    except ScopeError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
