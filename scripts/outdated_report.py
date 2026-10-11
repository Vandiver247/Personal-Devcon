#!/usr/bin/env python3
"""Report which pinned tools have newer versions available.

Prints a Markdown report to stdout. Always exits 0 when the report is
produced, whether or not anything is outdated: it is informational only.

Needs `mise` and `git` on PATH. Set GITHUB_TOKEN to avoid GitHub API rate limits.
Pass `--image REF` to also check the Neovim plugins, which needs `docker` and
runs lazy.nvim's own update check inside that image.
"""

import argparse
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

# Runs after `Lazy! check`, which fetches every plugin and records the ones whose
# installed commit differs from the commit their spec (branch or version) resolves to.
PLUGIN_CHECK_LUA = " ".join(
    """
    local has_errors = require("lazy.core.plugin").has_errors
    for _, plugin in ipairs(require("lazy").plugins()) do
      local updates = plugin._.updates
      local state = has_errors(plugin) and "error" or updates and "behind" or "current"
      local from = updates and updates.from.commit or ""
      local to = updates and updates.to.commit or ""
      io.stdout:write(("lazy-check\\t%s\\t%s\\t%s\\t%s\\n"):format(state, plugin.name, from, to))
    end
    """.split()
)


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


def fetch_json(url: str, headers: dict[str, str] | None = None):
    request = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)
    except (OSError, ValueError):
        return None


def github_latest_release(repo: str) -> str | None:
    headers = {"Accept": "application/vnd.github+json"}
    if token := os.environ.get("GITHUB_TOKEN"):
        headers["Authorization"] = f"Bearer {token}"
    release = fetch_json(f"https://api.github.com/repos/{repo}/releases/latest", headers)
    try:
        return release["tag_name"].lstrip("v")
    except (KeyError, TypeError):
        return None


def ubuntu_latest_lts() -> str | None:
    """Newest released Ubuntu LTS, so interim releases are never reported."""
    series = fetch_json("https://api.launchpad.net/devel/ubuntu/series")
    try:
        released = [
            entry["version"]
            for entry in series["entries"]
            if entry["status"] in ("Current Stable Release", "Supported")
        ]
    except (KeyError, TypeError):
        return None
    # LTS releases are the April (.04) releases of even years.
    lts = [v for v in released if re.fullmatch(r"\d\d\.04", v) and int(v[:2]) % 2 == 0]
    return max(lts, key=version_key, default=None)


def plugin_updates(image: str) -> tuple[int, list[tuple[str, str, str]]] | None:
    """Return (plugin count, [(name, installed, available)]) from lazy.nvim's check."""
    try:
        result = subprocess.run(
            ["docker", "run", "--rm", image, "nvim", "--headless",
             "+Lazy! check", f"+lua {PLUGIN_CHECK_LUA}", "+qa"],
            capture_output=True, text=True, timeout=600,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    plugins = [
        line.split("\t")[1:] for line in result.stdout.splitlines() if line.startswith("lazy-check\t")
    ]
    # A plugin that failed to fetch would otherwise look up to date.
    if not plugins or any(state == "error" for state, *_ in plugins):
        return None
    behind = [(name, old[:7], new[:7]) for state, name, old, new in plugins if state == "behind"]
    return len(plugins), behind


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
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--image", help="built image to run the Neovim plugin check in")
    args = parser.parse_args()

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

    pinned = search(r"(?m)^FROM ubuntu:([\d.]+)", "Dockerfile")
    latest = ubuntu_latest_lts()
    rows.append(("Ubuntu LTS (base image)", pinned, latest, latest is not None and is_newer(latest, pinned), "`Dockerfile`"))

    plugins = plugin_updates(args.image) if args.image else None
    count, behind = plugins or (None, [])
    rows.append((
        "Neovim plugins",
        f"{count} commits" if plugins else "n/a",
        plugins and (f"{len(behind)} behind" if behind else "all current"),
        bool(behind),
        "`nvim/lazy-lock.json`",
    ))

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
    if behind:
        print(f"<details><summary>Neovim plugins behind ({len(behind)})</summary>")
        print()
        print("| Plugin | Pinned | Latest |")
        print("|---|---|---|")
        for name, old, new in behind:
            print(f"| {name} | {old} | {new} |")
        print()
        print("</details>")
        print()
    print(
        "This report is informational and does not block merging. The Ubuntu row "
        "only tracks LTS releases. Not checked: apt packages and the patch level "
        "of the base image, which the weekly scheduled build picks up."
    )


if __name__ == "__main__":
    main()
