"""Fetches or checks Formula/landfall.rb, the formula a landfall release ships.

Usage:
  python3 -I scripts/landfall.py fetch [--allow-prerelease] <version> <formula-file>
  python3 -I scripts/landfall.py check <formula-file>
  python3 -I scripts/landfall.py check-tree [--offline-if-unchanged] <change-repo> <change-rev> <base-repo> <base-rev>

landfall's release workflow writes the finished formula and attaches it to the
release as landfall.rb, with a build provenance attestation. Both commands
download that asset and refuse it unless two independent checks pass:

1. The release's tag, v<version>, is an annotated tag whose SSH signature
   ssh-keygen verifies against the landfall-release key in
   landfall-release-signers, in this repository. A stolen GitHub token can run
   the release workflow, but it cannot sign a tag.
2. gh attestation verify finds that landfall's release workflow built the asset,
   on a GitHub-hosted runner, from the commit that signed tag names.

Release candidates never reach this tap: both commands refuse a version with a
pre-release suffix, and a release GitHub marks as a pre-release.
--allow-prerelease lifts that for fetch alone, to try the checks on a release
candidate, and then writes only a new file outside any git repository.

fetch writes the verified asset to the formula file. It never goes back: the
version must be no older than the formula already there, and, when the file is
in a git repository, than the highest version that path has had in its history.
The tap's bump workflow runs it, and so can a person. check reads the version
from the formula file and fails unless the file is byte for byte the verified
asset of that release.

check-tree is what CI runs, with this script and landfall-release-signers as
the pull request's base has them. It reads the change's commit from git, as
data, and compares it with the base commit and that commit's full history. It
refuses:

- a file named landfall.rb, in any case, anywhere but Formula/landfall.rb, and
  any other Formula/**/landfall*.rb, which Homebrew could load instead;
- an Aliases/ entry whose name or target is landfall, and a
  formula_renames.json or tap_migrations.json that mentions landfall, through
  which Homebrew could resolve landfall to another formula;
- Formula/landfall.rb as anything but a regular file;
- a change that drops the formula the base has;
- a formula that differs from the base one without a strictly newer version,
  or whose version is below the highest the formula has ever had there;
- and then anything check refuses.

With --offline-if-unchanged, which CI passes on a pull request, a formula byte
for byte the base's passes without the network checks: the base's was verified
when it merged. The checks above still run. A push to main checks it in full.

CI's scope check refuses any new file without the maintainer's signature, so
what check-tree does not look for, such as an external command, cannot arrive
in a bump either: the two together are the guarantee, not check-tree alone.

It needs Python 3.11 or later, git, ssh-keygen and an authenticated gh, and
nothing outside the standard library.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from collections.abc import Callable
from pathlib import Path

REPO = "pecheriere/landfall"
WORKFLOW = f"https://github.com/{REPO}/.github/workflows/release.yml"
IDENTITY = "landfall-release"
NAMESPACE = "git"
SIGNERS = Path(__file__).resolve().parent.parent / "landfall-release-signers"
ASSET = "landfall.rb"
FORMULA = "Formula/landfall.rb"
REGULAR_FILE = "100644"
STABLE = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+")
PRERELEASE = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+(-[0-9A-Za-z]+(\.[0-9A-Za-z]+)*)?")
COMMIT = re.compile(r"[0-9a-f]{40}")
BEGIN = b"-----BEGIN SSH SIGNATURE-----\n"
END = b"-----END SSH SIGNATURE-----\n"


def git_env(environ: dict[str, str]) -> dict[str, str]:
    """The environment git runs in: no inherited GIT_ variable, and no user or
    system configuration, so that nothing like a url insteadOf rule can change
    where the tag comes from."""
    clean = {key: value for key, value in environ.items() if not key.startswith("GIT_")}
    return {**clean, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1", "GIT_TERMINAL_PROMPT": "0"}


GIT_ENV = git_env(dict(os.environ))


class LandfallError(Exception):
    pass


def check_version(version: str, allow_prerelease: bool = False) -> None:
    if (STABLE if not allow_prerelease else PRERELEASE).fullmatch(version):
        return
    if PRERELEASE.fullmatch(version):
        raise LandfallError(f"{version} is a pre-release, and release candidates never reach this tap")
    raise LandfallError(f"not a release version: {version!r}")


def is_prerelease(version: str) -> bool:
    """Whether GitHub marks the release v<version> as a pre-release."""
    if shutil.which("gh") is None:
        raise LandfallError("gh is not installed, so the release cannot be looked up")
    out = run(
        ["gh", "api", "--hostname", "github.com", f"repos/{REPO}/releases/tags/v{version}"],
        f"looking up release v{version}",
    )
    try:
        flag = json.loads(out)["prerelease"]
    except (ValueError, KeyError, TypeError) as error:
        raise LandfallError(f"release v{version} has no pre-release flag") from error
    if not isinstance(flag, bool):
        raise LandfallError(f"release v{version} has a pre-release flag that is not true or false")
    return flag


def download(version: str) -> bytes:
    """The release's landfall.rb asset, over HTTPS."""
    url = f"https://github.com/{REPO}/releases/download/v{version}/{ASSET}"
    try:
        with urllib.request.urlopen(url, timeout=60) as response:
            return response.read()
    except OSError as error:
        raise LandfallError(f"downloading {url} failed: {error}") from error


def run(args: list[str], what: str, env: dict[str, str] | None = None) -> bytes:
    try:
        result = subprocess.run(args, capture_output=True, check=False, env=env)
    except OSError as error:
        raise LandfallError(f"{what} failed: {error}") from error
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", "replace").strip()
        raise LandfallError(f"{what} failed: {detail}")
    return result.stdout


def raw_tag(version: str) -> bytes:
    """The raw tag object v<version>, fetched from landfall's repository."""
    ref = f"refs/tags/v{version}"
    with tempfile.TemporaryDirectory() as tmp:
        git = ["git", "-C", tmp]
        run(["git", "init", "-q", "--bare", tmp], "git init", env=GIT_ENV)
        run(
            git + ["fetch", "-q", "--no-tags", "--depth=1", f"https://github.com/{REPO}.git", f"+{ref}:{ref}"],
            f"fetching {ref}",
            env=GIT_ENV,
        )
        kind = run(git + ["cat-file", "-t", ref], "git cat-file", env=GIT_ENV).strip()
        if kind != b"tag":
            raise LandfallError(f"{ref} is not an annotated tag, so it carries no signature")
        return run(git + ["cat-file", "tag", ref], "git cat-file", env=GIT_ENV)


def split_tag(raw: bytes, version: str) -> tuple[str, bytes, bytes]:
    """The commit a tag object names, the payload its signature covers, and the signature.

    Refuses anything but exactly one SSH signature at the end, and a header other
    than object, type commit, tag v<version> and tagger, in that order.
    """
    if raw.count(b"-----BEGIN ") != 1 or raw.count(b"-----END ") != 1:
        raise LandfallError(f"tag v{version} does not carry exactly one signature")
    start = raw.find(BEGIN)
    if start <= 0 or raw[start - 1 : start] != b"\n" or not raw.endswith(END):
        raise LandfallError(f"tag v{version} does not end with an SSH signature")
    payload, signature = raw[:start], raw[start:]
    header, sep, _ = payload.partition(b"\n\n")
    try:
        lines = header.decode("utf-8").split("\n")
    except UnicodeDecodeError as error:
        raise LandfallError(f"tag v{version} has a header that is not UTF-8") from error
    if not sep or len(lines) != 4:
        raise LandfallError(f"tag v{version} has an unexpected header")
    kind, _, commit = lines[0].partition(" ")
    if kind != "object" or not COMMIT.fullmatch(commit):
        raise LandfallError(f"tag v{version} names no object")
    if lines[1] != "type commit":
        raise LandfallError(f"tag v{version} does not name a commit")
    if lines[2] != f"tag v{version}":
        raise LandfallError(f"tag v{version}'s object is named {lines[2]!r}")
    if not lines[3].startswith("tagger "):
        raise LandfallError(f"tag v{version} has no tagger")
    return commit, payload, signature


def verify_signature(payload: bytes, signature: bytes, signers: Path) -> None:
    """Fails unless the signature is a good git one from a key listed for landfall-release."""
    with tempfile.TemporaryDirectory() as tmp:
        sig = Path(tmp) / "tag.sig"
        sig.write_bytes(signature)
        result = subprocess.run(
            ["ssh-keygen", "-Y", "verify", "-f", str(signers), "-I", IDENTITY, "-n", NAMESPACE, "-s", str(sig)],
            input=payload,
            capture_output=True,
            check=False,
        )
    if result.returncode != 0:
        raise LandfallError(f"the tag's signature does not verify against {signers.name}")


def attestation_command(path: Path, version: str, commit: str) -> list[str]:
    if not COMMIT.fullmatch(commit):
        raise LandfallError(f"not a commit: {commit!r}; an empty --source-digest would check nothing")
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
        f"--source-digest={commit}",
        "--deny-self-hosted-runners",
    ]


def attest(path: Path, version: str, commit: str) -> None:
    """Fails unless gh verifies the file's provenance: landfall's release workflow at that tag and commit."""
    command = attestation_command(path, version, commit)
    if shutil.which("gh") is None:
        raise LandfallError("gh is not installed, so the attestation cannot be checked")
    run(command, f"gh attestation verify for {ASSET} of v{version}")


def formula_version(text: str) -> str:
    """The version a formula declares on its own version line."""
    found = re.findall(r'^  version "([^"\n]*)"$', text, flags=re.MULTILINE)
    if len(found) != 1:
        raise LandfallError("the formula does not declare exactly one version")
    check_version(found[0], allow_prerelease=True)
    return found[0]


def verified_formula(
    version: str,
    allow_prerelease: bool = False,
    signers: Path = SIGNERS,
    prerelease: Callable[[str], bool] = is_prerelease,
    get: Callable[[str], bytes] = download,
    get_tag: Callable[[str], bytes] = raw_tag,
    attest_file: Callable[[Path, str, str], None] = attest,
) -> bytes:
    """The release's landfall.rb, once its tag's signature and its attestation both check out."""
    check_version(version, allow_prerelease)
    if not allow_prerelease and prerelease(version):
        raise LandfallError(f"GitHub marks v{version} as a pre-release, and release candidates never reach this tap")
    commit, payload, signature = split_tag(get_tag(version), version)
    verify_signature(payload, signature, signers)
    asset = get(version)
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / ASSET
        path.write_bytes(asset)
        attest_file(path, version, commit)
    try:
        declared = formula_version(asset.decode("utf-8"))
    except UnicodeDecodeError as error:
        raise LandfallError(f"v{version}'s {ASSET} is not UTF-8") from error
    if declared != version:
        raise LandfallError(f"v{version}'s {ASSET} declares version {declared}")
    return asset


def decoded_version(text: bytes, what: str) -> str:
    try:
        return formula_version(text.decode("utf-8"))
    except UnicodeDecodeError as error:
        raise LandfallError(f"{what} is not UTF-8") from error


def version_key(version: str) -> tuple[int, ...]:
    check_version(version)
    return tuple(int(part) for part in version.split("."))


def refuse_downgrade(text: bytes, version: str, base: bytes | None, floor: str | None) -> None:
    """Fails unless the formula is the base one unchanged, or moves to a newer release.

    A changed formula must be strictly newer than the base, and never below the
    floor, the highest version the formula has had on the trusted branch.
    """
    if text == base:
        return
    if base is not None:
        old = decoded_version(base, "the base formula")
        if version_key(version) <= version_key(old):
            raise LandfallError(f"refusing to go from landfall {old} to {version}: a change must move to a newer one")
    if floor is not None and version_key(version) < version_key(floor):
        raise LandfallError(f"refusing landfall {version}: the formula has already been at {floor}")


def check(
    text: bytes,
    base: bytes | None = None,
    floor: str | None = None,
    verified: Callable[[str], bytes] = verified_formula,
) -> str:
    """The formula's version, if the formula is exactly that release's verified asset.

    With a base, the formula it replaces, and a floor, the highest version it
    has had, refuse_downgrade must also pass.
    """
    version = decoded_version(text, "the formula")
    check_version(version)
    refuse_downgrade(text, version, base, floor)
    if text != verified(version):
        raise LandfallError(f"the formula is not v{version}'s verified {ASSET}")
    return version


def stray_formulas(paths: list[str]) -> list[str]:
    """Paths Homebrew could take for landfall's formula, other than Formula/landfall.rb.

    That is any file or directory named landfall.rb, in any case, and anything
    under Formula/ named landfall*.rb.
    """
    stray = set()
    for path in paths:
        parts = path.split("/")
        for depth, name in enumerate(parts, start=1):
            sub = "/".join(parts[:depth])
            lower = name.lower()
            variant = parts[0] == "Formula" and depth > 1 and lower.startswith("landfall") and lower.endswith(".rb")
            if sub != FORMULA and (lower == ASSET or variant):
                stray.add(sub)
    return sorted(stray)


# Files Homebrew reads to resolve a formula name to another formula.
POINTER_FILES = ("formula_renames.json", "tap_migrations.json")


def names_landfall(text: str) -> bool:
    """Whether a name, path or tap reference ends in something called landfall."""
    return text.strip().rsplit("/", 1)[-1].lower().startswith("landfall")


def json_strings(data: object) -> list[str]:
    """Every key and string value in a JSON document."""
    if isinstance(data, str):
        return [data]
    if isinstance(data, dict):
        return [string for key, value in data.items() for string in [key, *json_strings(value)]]
    if isinstance(data, list):
        return [string for item in data for string in json_strings(item)]
    return []


def stray_pointers(paths: list[str], read: Callable[[str], bytes]) -> list[str]:
    """Files through which Homebrew could resolve landfall to something else.

    That is an Aliases/ entry whose name or target is landfall, and a
    formula_renames.json or tap_migrations.json that mentions landfall.
    """
    stray = []
    for path in paths:
        # Casefolded, because Homebrew on a case-insensitive disk reads
        # aliases/ or Formula_Renames.json as well.
        parts = path.casefold().split("/")
        if parts[0] == "aliases" and len(parts) > 1:
            if names_landfall(parts[-1]) or names_landfall(read(path).decode("utf-8", "replace")):
                stray.append(path)
        elif path.casefold() in POINTER_FILES:
            try:
                data = json.loads(read(path))
            except ValueError as error:
                raise LandfallError(f"{path} is not JSON, so it cannot be checked for landfall") from error
            if any(names_landfall(string) for string in json_strings(data)):
                stray.append(path)
    return sorted(stray)


def git(repository: Path, *args: str) -> bytes:
    return run(["git", "-C", str(repository), *args], f"git {args[0]}", env=GIT_ENV)


def commit_of(repository: Path, revision: str) -> str:
    return git(repository, "rev-parse", "--verify", "--end-of-options", f"{revision}^{{commit}}").decode().strip()


def tree_modes(repository: Path, commit: str) -> dict[str, str]:
    """Each path in the commit's tree, with its mode, as git stores it."""
    modes = {}
    for record in git(repository, "ls-tree", "-r", "-z", "--full-tree", commit).split(b"\0"):
        if record:
            meta, _, path = record.partition(b"\t")
            modes[path.decode("utf-8", "surrogateescape")] = meta.split(b" ", 1)[0].decode()
    return modes


def formula_at(repository: Path, commit: str, path: str = FORMULA) -> bytes | None:
    """The formula as the commit has it, or None if it has none."""
    if not git(repository, "ls-tree", "--name-only", commit, "--", path).strip():
        return None
    return git(repository, "show", f"{commit}:{path}")


def highest(versions: list[str]) -> str | None:
    """The highest stable version among them; a file that never declared one adds nothing."""
    stable = [version for version in versions if STABLE.fullmatch(version)]
    return max(stable, key=version_key, default=None)


def history(repository: Path, revision: str, path: str = FORMULA) -> list[str]:
    """Every version the formula has declared up to the revision."""
    if git(repository, "rev-parse", "--is-shallow-repository").strip() != b"false":
        raise LandfallError(f"{repository} is a shallow clone, so the formula's history is incomplete")
    versions = []
    # --full-history: without it, git skips a line of history that a merge
    # undid, and with it the highest version that line had.
    for commit in git(repository, "log", "--full-history", "--format=%H", revision, "--", path).decode().split():
        text = formula_at(repository, commit, path)
        if text is None:
            continue
        try:
            versions.append(decoded_version(text, f"{path} at {commit}"))
        except LandfallError:
            continue
    return versions


def judge_tree(
    head: bytes | None,
    base: bytes | None,
    floor: str | None,
    check_formula: Callable[[bytes, bytes | None, str | None], str] = check,
    offline_if_unchanged: bool = False,
) -> str:
    """What check-tree concludes, from the change's formula, the base one and the floor.

    With offline_if_unchanged, a formula identical to the base's is not verified
    again over the network.
    """
    if offline_if_unchanged and head is not None and head == base:
        return f"{FORMULA} is unchanged from the base, which was verified when it merged: not verified again"
    if head is None:
        if base is not None:
            raise LandfallError(
                f"this change deletes {FORMULA}, which the base has; going back to no formula is not a bump, "
                "so the maintainer merges it by hand if it is meant"
            )
        return f"no {FORMULA}, and the base has none: nothing to check"
    version = check_formula(head, base, floor)
    return f"{FORMULA} is landfall {version}'s verified formula"


def check_tree(
    change: Path,
    change_revision: str,
    base: Path,
    base_revision: str,
    check_formula: Callable[[bytes, bytes | None, str | None], str] = check,
    offline_if_unchanged: bool = False,
) -> str:
    """check-tree: the change's commit, read from git as data, against the base commit and its history."""
    commit = commit_of(change, change_revision)
    modes = tree_modes(change, commit)
    stray = stray_formulas(list(modes)) + stray_pointers(
        list(modes), lambda path: git(change, "show", f"{commit}:{path}")
    )
    if stray:
        raise LandfallError(f"only {FORMULA} may hold landfall's formula, but the change also has {', '.join(stray)}")
    if "Formula" in modes:
        raise LandfallError("Formula is not a directory")
    mode = modes.get(FORMULA)
    if mode not in (None, REGULAR_FILE):
        raise LandfallError(f"{FORMULA} is not a regular file (mode {mode})")
    head = git(change, "show", f"{commit}:{FORMULA}") if mode else None
    base_commit = commit_of(base, base_revision)
    base_formula = formula_at(base, base_commit)
    floor = highest(history(base, base_commit))
    return judge_tree(head, base_formula, floor, check_formula, offline_if_unchanged)


def work_tree(path: Path) -> Path | None:
    """The top of the git work tree the path is in, or None if it is in none."""
    directory = path.resolve().parent
    while not directory.exists():
        directory = directory.parent
    result = subprocess.run(
        ["git", "-C", str(directory), "rev-parse", "--show-toplevel"], capture_output=True, check=False, env=GIT_ENV
    )
    return Path(result.stdout.decode().strip()) if result.returncode == 0 else None


def fetch_formula(
    version: str,
    out: Path,
    allow_prerelease: bool = False,
    verified: Callable[..., bytes] | None = None,
) -> str:
    """fetch: writes the verified formula to out, never going back.

    The formula already at out is the base, and when out is in a git work tree,
    the highest version that path has had there is the floor. A release
    candidate, with --allow-prerelease, goes only to a new file outside any
    work tree.
    """
    verified = verified or verified_formula
    if allow_prerelease:
        if out.exists() or work_tree(out) is not None:
            raise LandfallError("--allow-prerelease writes only a new file, outside any git repository")
        out.write_bytes(verified(version, True))
        return f"wrote landfall {version}'s verified formula to {out}"
    check_version(version)
    base = out.read_bytes() if out.exists() else None
    top = work_tree(out)
    floor = highest(history(top, "HEAD", out.resolve().relative_to(top.resolve()).as_posix())) if top else None
    old = decoded_version(base, str(out)) if base is not None else None
    for bound in (old, floor):
        if bound is not None and version_key(version) < version_key(bound):
            raise LandfallError(f"refusing to go from landfall {bound} to {version}")
    asset = verified(version)
    if asset == base:
        return f"{out} is already landfall {version}'s verified formula"
    refuse_downgrade(asset, version, base, floor)
    out.write_bytes(asset)
    return f"wrote landfall {version}'s verified formula to {out}"


def read(path: str) -> bytes:
    try:
        return Path(path).read_bytes()
    except OSError as error:
        raise LandfallError(f"cannot read {path}: {error}") from error


def main(argv: list[str]) -> int:
    try:
        args = argv[1:]
        allow = args[:1] == ["--allow-prerelease"]
        if allow:
            args = args[1:]
        if argv[:1] == ["fetch"] and len(args) == 2:
            print(fetch_formula(args[0], Path(args[1]), allow))
            return 0
        if argv[:1] == ["check"] and len(argv) == 2:
            version = check(read(argv[1]))
            print(f"{argv[1]} is landfall {version}'s verified formula")
            return 0
        offline = argv[1:2] == ["--offline-if-unchanged"]
        tree_args = argv[1 + offline :]
        if argv[:1] == ["check-tree"] and len(tree_args) == 4:
            change, change_revision, base, base_revision = tree_args
            print(check_tree(Path(change), change_revision, Path(base), base_revision, offline_if_unchanged=offline))
            return 0
    except LandfallError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(__doc__.split("\n\n")[1], file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
