#!/usr/bin/env python3
"""Report which pinned tools have newer versions available.

Prints a Markdown report to stdout. Always exits 0 when the report is
produced, whether or not anything is outdated: it is informational only.

Needs `mise` and `git` on PATH. Set GITHUB_TOKEN to avoid GitHub API rate limits.
"""

import json
import os
import re
import subprocess
import tempfile
import tomllib
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MARKER = "<!-- outdated-report -->"


def run(*cmd: str) -> str | None:
    # Run outside the repo so mise doesn't load (or ask to trust) the project config.
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=120, cwd=tempfile.gettempdir()
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    lines = result.stdout.strip().splitlines()
    return lines[-1].strip() if lines else None


def mise_latest(tool: str) -> str | None:
    return run("mise", "latest", tool)


def github_latest_release(repo: str) -> str | None:
    request = urllib.request.Request(
        f"https://api.github.com/repos/{repo}/releases/latest",
        headers={"Accept": "application/vnd.github+json"},
    )
    if token := os.environ.get("GITHUB_TOKEN"):
        request.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)["tag_name"].lstrip("v")
    except (OSError, KeyError, ValueError):
        return None


def version_key(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in re.findall(r"\d+", version))


def is_newer(latest: str, pinned: str) -> bool:
    return version_key(latest) > version_key(pinned)


def search(pattern: str, path: str) -> str:
    match = re.search(pattern, (ROOT / path).read_text())
    if not match:
        raise SystemExit(f"could not find {pattern!r} in {path}")
    return match.group(1)


def main() -> None:
    tools = tomllib.loads((ROOT / "mise.toml").read_text())["tools"]
    with ThreadPoolExecutor(max_workers=8) as pool:
        latest_versions = list(pool.map(mise_latest, tools))

    # (name, pinned, latest, outdated, pinned in)
    rows = [
        (name, pinned, latest, latest is not None and is_newer(latest, pinned), "`mise.toml`")
        for (name, pinned), latest in zip(tools.items(), latest_versions)
    ]

    pinned = search(r"ARG MISE_VERSION=(\S+)", "Dockerfile")
    latest = github_latest_release("jdx/mise")
    rows.append(("mise", pinned, latest, latest is not None and is_newer(latest, pinned), "`Dockerfile`"))

    pinned = search(r'version\s*=\s*"([^"]+)"', "nvim/lazyvim-pin.lua")
    latest = github_latest_release("LazyVim/LazyVim")
    rows.append(("LazyVim", pinned, latest, latest is not None and is_newer(latest, pinned), "`nvim/lazyvim-pin.lua`"))

    pinned = search(r"ARG LAZYVIM_STARTER_COMMIT=(\S+)", "Dockerfile")
    head = run("git", "ls-remote", "https://github.com/LazyVim/starter.git", "HEAD")
    latest = head.split()[0] if head else None
    rows.append(("LazyVim starter", pinned[:7], latest and latest[:7], latest is not None and latest != pinned, "`Dockerfile`"))

    pinned = search(r'trivy_image := "aquasec/trivy:([^@"]+)', "justfile")
    latest = github_latest_release("aquasecurity/trivy")
    rows.append(("trivy", pinned, latest, latest is not None and is_newer(latest, pinned), "`justfile`"))

    outdated = [row for row in rows if row[3]]
    unknown = [row for row in rows if row[2] is None]

    print(MARKER)
    print("## Tool version report")
    print()
    if outdated:
        print(f"**{len(outdated)} of {len(rows)}** pinned tools have a newer version available.")
    else:
        print(f"All {len(rows) - len(unknown)} tools that could be checked are on their latest version.")
    if unknown:
        print(f"The latest version could not be determined for {len(unknown)}.")
    print()
    print("| Tool | Pinned | Latest | Status | Pinned in |")
    print("|---|---|---|---|---|")
    # Outdated first, then unknown, then up to date.
    for name, pinned, latest, is_outdated, where in sorted(rows, key=lambda r: (not r[3], r[2] is not None)):
        if latest is None:
            status = "❓ unknown"
        elif is_outdated:
            status = "⬆️ update available"
        else:
            status = "✅ up to date"
        print(f"| {name} | {pinned} | {latest or 'n/a'} | {status} | {where} |")
    print()
    print(
        "This report is informational and does not block merging. Not checked: "
        "the Ubuntu base image, apt packages, and the Neovim plugin commits in "
        "`nvim/lazy-lock.json`."
    )


if __name__ == "__main__":
    main()
