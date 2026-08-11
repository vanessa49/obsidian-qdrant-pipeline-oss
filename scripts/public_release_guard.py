#!/usr/bin/env python3
"""Fail when the tracked tree contains obvious private runtime state or secrets.

This guard intentionally checks the current Git tree only. The public release is
created later from a clean `git archive` snapshot in a new repository, so this
also blocks known internal examples from re-entering the staged source tree.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

FORBIDDEN_PATHS = {
    ".env",
    "config.yaml",
    "config.local.yaml",
    "app_desktop/config_local.yaml",
}

FORBIDDEN_PREFIXES = (
    "qdrant_data/",
    "vault/",
    "kb-inbox/",
    "inbox/",
    "app_desktop/qdrant_data/",
    "app_desktop/bundled_kb/",
    "app_desktop/bundled_ollama/",
    "app_desktop/dist/",
    "app_desktop/build/",
)

TEXT_PATTERNS = {
    "RFC1918 private IPv4 address": re.compile(
        r"(?<![0-9])(?:10[.](?:[0-9]{1,3}[.]){2}[0-9]{1,3}|"
        r"192[.]168[.][0-9]{1,3}[.][0-9]{1,3}|"
        r"172[.](?:1[6-9]|2[0-9]|3[01])[.][0-9]{1,3}[.][0-9]{1,3})(?![0-9])"
    ),
    "Windows user-profile path": re.compile(r"[A-Za-z]:[\\/]Users[\\/][^\\/\s]+", re.IGNORECASE),
    "Windows absolute path": re.compile(r"(?<![A-Za-z0-9])[A-Za-z]:[\\/]"),
    "NVIDIA API key-like token": re.compile(r"nvapi-[A-Za-z0-9_-]{8,}"),
    "OpenAI-style secret-like token": re.compile(r"sk-[A-Za-z0-9_-]{16,}"),
    "private key material": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "known internal project example": re.compile(r"Z7用户体验项目定性"),
    "known internal participant example": re.compile(r"Z7使用体验调研谢"),
    "known internal research example": re.compile(r"2021年初中生生活形态调研"),
    "known internal product-study example": re.compile(r"Z10\s*NPS", re.IGNORECASE),
    "unresolved private reference-project name": re.compile(r"\b(?:openhuman|insuraassi(?:-ref)?)\b", re.IGNORECASE),
}

# Documentation may name the scanner patterns and local-only filenames as part
# of the safety mechanism. Exclude the scanner itself to avoid self-matches.
TEXT_SCAN_EXCLUDES = {
    "scripts/public_release_guard.py",
    # These release-operational and legacy packaging notes are intentionally
    # excluded from the clean public archive by .gitattributes. L6 verifies
    # their absence from the actual export.
    "docs/PUBLIC_RELEASE_LOCAL_CODEX_HANDOFF.md",
    "docs/PUBLIC_RELEASE_NOTES_DRAFT.md",
    "app_desktop/BUILD_GUIDE.md",
    "app_desktop/DEPLOYMENT.md",
    "app_desktop/QUICKREF.md",
    "app_desktop/SUMMARY.md",
}


def tracked_files() -> list[str]:
    output = subprocess.check_output(["git", "ls-files", "-z"])
    return [item.decode("utf-8") for item in output.split(b"\0") if item]


def main() -> int:
    problems: list[str] = []

    for rel in tracked_files():
        normalized = rel.replace("\\", "/")
        if normalized in FORBIDDEN_PATHS or normalized.startswith(FORBIDDEN_PREFIXES):
            problems.append(f"forbidden tracked path: {normalized}")
            continue

        if normalized in TEXT_SCAN_EXCLUDES:
            continue

        path = Path(rel)
        try:
            data = path.read_bytes()
        except OSError as exc:
            problems.append(f"could not read tracked file {normalized}: {exc}")
            continue

        if b"\x00" in data:
            continue

        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            continue

        for label, pattern in TEXT_PATTERNS.items():
            match = pattern.search(text)
            if match:
                preview = match.group(0)
                if "key" in label.lower() or "secret" in label.lower():
                    preview = preview[:5] + "…"
                problems.append(f"{normalized}: {label}: {preview}")

    if problems:
        print("PUBLIC_RELEASE_GUARD = FAIL")
        for problem in problems:
            print(f"- {problem}")
        print("\nFix the tracked tree before exporting a public release snapshot.")
        return 1

    print("PUBLIC_RELEASE_GUARD = PASS")
    print("Current tracked tree contains no blocked runtime paths or known private/internal patterns.")
    print("NOTE: the existing private repository history is not a publication surface; export a clean snapshot into a new repository.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
