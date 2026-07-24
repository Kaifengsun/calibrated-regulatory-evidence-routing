"""Privacy checks for files tracked by the Pilot repository."""

from __future__ import annotations

import re
import subprocess
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

DEFAULT_MAX_BYTES = 5_000_000

_RESTRICTED_NAMES = {
    ".env",
    "local.yaml",
    "local.yml",
}
_RESTRICTED_SUFFIXES = {
    ".7z",
    ".backup",
    ".bak",
    ".db",
    ".dump",
    ".faiss",
    ".pkl",
    ".sqlite",
    ".sqlite3",
    ".tar",
    ".zip",
}
_RESTRICTED_PARTS = {
    "corpus",
    "model_cache",
    "neo4j_docker_data",
    "private",
    "raw",
}
_TEXT_SUFFIXES = {
    "",
    ".cfg",
    ".csv",
    ".ini",
    ".json",
    ".jsonl",
    ".md",
    ".py",
    ".toml",
    ".tsv",
    ".txt",
    ".yaml",
    ".yml",
}
_ABSOLUTE_PATH_PATTERNS = (
    re.compile(r"(?i)\b[A-Z]:\\(?:Users|Projects)\\"),
    re.compile(r"(?<![A-Za-z0-9_])/(?:home|Users)/[^/\s]+/"),
)
_SECRET_ASSIGNMENT = re.compile(
    r"""(?im)^\s*(?:export\s+)?"""
    r"""(?P<key>[A-Z0-9_]*(?:PASSWORD|API_KEY|SECRET|TOKEN)[A-Z0-9_]*)"""
    r"""\s*[:=]\s*["']?(?P<value>[^\s#"'{}<>]+)"""
)
_SAFE_SECRET_VALUES = {
    "",
    "changeme",
    "change-me",
    "example",
    "none",
    "null",
    "placeholder",
    "redacted",
}
_SAFE_NON_SECRET_KEYS = {
    "false_token",
    "maximum_input_tokens",
    "tokenizer_revision",
    "true_token",
}


@dataclass(frozen=True)
class PrivacyFinding:
    path: str
    rule: str
    message: str


def _tracked_files(root: Path) -> list[str]:
    completed = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=root,
        check=True,
        capture_output=True,
    )
    return [item.decode("utf-8") for item in completed.stdout.split(b"\0") if item]


def _path_findings(relative: Path, size: int, max_bytes: int) -> list[PrivacyFinding]:
    normalized = relative.as_posix()
    lowered_parts = {part.casefold() for part in relative.parts}
    findings: list[PrivacyFinding] = []
    if relative.name.casefold() in _RESTRICTED_NAMES:
        findings.append(PrivacyFinding(normalized, "restricted-name", "local configuration"))
    if relative.suffix.casefold() in _RESTRICTED_SUFFIXES:
        findings.append(PrivacyFinding(normalized, "restricted-suffix", "binary or archived data"))
    if lowered_parts & _RESTRICTED_PARTS:
        findings.append(PrivacyFinding(normalized, "restricted-directory", "restricted data area"))
    if size > max_bytes:
        findings.append(
            PrivacyFinding(normalized, "oversize-file", f"{size} bytes exceeds {max_bytes}")
        )
    return findings


def _content_findings(relative: Path, text: str) -> list[PrivacyFinding]:
    normalized = relative.as_posix()
    findings: list[PrivacyFinding] = []
    for pattern in _ABSOLUTE_PATH_PATTERNS:
        if pattern.search(text):
            findings.append(
                PrivacyFinding(normalized, "absolute-path", "machine-local absolute path")
            )
            break
    for match in _SECRET_ASSIGNMENT.finditer(text):
        key = match.group("key").strip().casefold()
        value_raw = match.group("value").strip()
        value = value_raw.casefold()
        if key in _SAFE_NON_SECRET_KEYS:
            continue
        if key.startswith("_"):
            continue
        if key.endswith("_env"):
            continue
        if re.fullmatch(
            r"[A-Z][A-Z0-9_]*(?:PASSWORD|API_KEY|SECRET|TOKEN)[A-Z0-9_]*",
            value_raw,
        ):
            continue
        if value.startswith("$") or value in _SAFE_SECRET_VALUES:
            continue
        findings.append(
            PrivacyFinding(normalized, "possible-secret", "credential-like tracked assignment")
        )
        break
    return findings


def scan_tracked_files(
    root: Path,
    *,
    tracked_files: Iterable[str] | None = None,
    max_bytes: int = DEFAULT_MAX_BYTES,
) -> list[PrivacyFinding]:
    """Return deterministic findings for tracked or explicitly supplied files."""
    root = root.resolve()
    files = sorted(tracked_files if tracked_files is not None else _tracked_files(root))
    findings: list[PrivacyFinding] = []
    for item in files:
        relative = Path(item)
        path = root / relative
        if not path.is_file():
            findings.append(
                PrivacyFinding(relative.as_posix(), "missing-tracked-file", "file is not present")
            )
            continue
        findings.extend(_path_findings(relative, path.stat().st_size, max_bytes))
        if relative.suffix.casefold() not in _TEXT_SUFFIXES:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            findings.append(
                PrivacyFinding(relative.as_posix(), "non-utf8-text", "cannot decode as UTF-8")
            )
            continue
        findings.extend(_content_findings(relative, text))
    return sorted(findings, key=lambda row: (row.path, row.rule, row.message))


def main() -> int:
    findings = scan_tracked_files(Path.cwd())
    for finding in findings:
        print(f"{finding.path}: {finding.rule}: {finding.message}")
    if findings:
        return 1
    print("privacy scan passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
