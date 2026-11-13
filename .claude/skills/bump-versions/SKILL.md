---
name: bump-versions
description: Scan the personal-devcon image for newer versions of the base image, every pinned tool, the Neovim plugins and the packages bundled inside the image, then apply the bumps on a branch, rebuild, test, scan and commit. Use when asked to update, bump or refresh versions in this repo.
---

# Bump versions

Update every version the image pins, verify the image still works, and commit
the result on a branch. Don't push or open a PR without asking first.

Run everything from the repo root. Keep logs and temporary files in the
session scratchpad, not the repo.

## 1. Prepare

```sh
git status --short              # must be clean
git checkout -b bump-tool-versions-$(date +%Y-%m)
export GITHUB_TOKEN="$(gh auth token)"   # avoids GitHub API rate limits in mise and the report
SCRATCH=...                              # the session scratchpad directory (or a mktemp -d)
```

Shell state doesn't persist between commands, so repeat these exports
wherever they're needed.

Read the most recent "Bump pinned tool versions" commit (`git log --grep 'Bump pinned'`)
and match its commit message format.

## 2. Scan

Build the current checkout first. The plugin check runs inside the built image,
and the build pulls the current `ubuntu:26.04` digest.

```sh
just build > "$SCRATCH/build-before.log" 2>&1
just outdated
```

`just outdated` (`scripts/outdated_report.py`) covers the mise tools, mise
itself, LazyVim, the LazyVim starter commit, Trivy, the Ubuntu LTS release and
the Neovim plugins. It does **not** cover the following, so check them yourself:

- **apt packages and the base image's patch level:**
  `docker run --rm vandiver247/personal-devcon:latest bash -c 'sudo apt-get update -qq >/dev/null 2>&1; apt list --upgradable 2>/dev/null; grep VERSION= /etc/os-release'`.
  apt packages aren't pinned, so anything upgradable just means the base image
  is stale. A rebuild with `docker build --pull` picks up the fix.
- **Packages bundled with node and python:** compare the image's `npm --version`
  with `npm view npm version`, and its `python -m pip --version` with
  `pip index versions pip`. npm and pip are not pinned separately. Report a
  newer version, but don't add a pin unless the user asks for one, especially
  for a new major version.
- **The just version in the workflows:** `just-version:` in every file under
  `.github/workflows/`. Keep it the same as `just` in `mise.toml`.
- **GitHub Actions:** Dependabot bumps these, so leave them alone.

## 3. Apply the bumps

| What | How |
|---|---|
| Tools in `mise.toml` | Edit each version in place and keep the comments |
| mise | `ARG MISE_VERSION` in the `Dockerfile`. Also update both checksums from the release: `curl -fsSL https://github.com/jdx/mise/releases/download/v$V/SHASUMS256.txt \| grep -E "mise-v$V-linux-(x64\|arm64)$"`. x64 goes in `MISE_SHA256_AMD64`, arm64 in `MISE_SHA256_ARM64` |
| LazyVim | `version` in `nvim/lazyvim-pin.lua` |
| LazyVim starter | `ARG LAZYVIM_STARTER_COMMIT` in the `Dockerfile`, as the full SHA from `git ls-remote https://github.com/LazyVim/starter.git HEAD` |
| Trivy | `trivy_image` in the `justfile`. It's pinned by tag and digest, so update both: `docker buildx imagetools inspect aquasec/trivy:$V \| grep -m1 Digest` |
| just | `mise.toml` and every `just-version:` in `.github/workflows/` |
| Ubuntu | `FROM ubuntu:` in the `Dockerfile`, and only for a new LTS. The report already ignores interim releases |

After editing, grep the repo (excluding `.git`) for each old version string to
catch any copies you missed.

## 4. Refresh the plugin lockfile

Do this whenever LazyVim was bumped or the report lists plugins as behind.
Rebuild, run a sync inside the image, then copy the lockfile back:

```sh
just build > "$SCRATCH/build-after.log" 2>&1
docker run --rm vandiver247/personal-devcon:latest bash -c \
  'nvim --headless "+Lazy! sync" +qa >/dev/null 2>&1; cat ~/.config/nvim/lazy-lock.json' \
  > "$SCRATCH/lazy-lock.json"
cp "$SCRATCH/lazy-lock.json" nvim/lazy-lock.json
git diff nvim/lazy-lock.json
```

Make sure the `LazyVim` commit in the lockfile is the commit of the new tag:
`git ls-remote https://github.com/LazyVim/LazyVim.git refs/tags/v$V`. A sync
can still move other plugins when the report said they were current. That's
expected, because a new LazyVim release changes the plugin specs.

## 5. Verify

```sh
just test        # rebuilds, then checks that every pinned tool is installed and runs
just outdated    # should now report every tool on its latest version
just scan        # Trivy: fails on any critical, or any high with a fix available
```

If `just test` fails, read the error. Release notes often explain a renamed
binary or a changed `--version` output. Fix the problem, or roll back only that
tool and report it.

`just scan` often fails because of findings the bumps didn't cause. For each
high or critical finding, list the target binary it's in:

```sh
python3 -I -c '
import json, sys
for r in json.load(open(sys.argv[1])).get("Results", []):
    for v in r.get("Vulnerabilities") or []:
        if v["Severity"] in ("HIGH", "CRITICAL"):
            print(v["Severity"], v["VulnerabilityID"], v["PkgName"], v["InstalledVersion"], "->", v.get("FixedVersion", ""), "|", r["Target"])
' trivy-results.json | sort -u
```

Group the findings by where they come from:
- a tool that has a newer release (bump it)
- a tool already at its latest release, which embeds outdated Go modules or an
  outdated Go standard library
- Node's or Python's bundled packages
- OS packages with no fixed version yet

Only the first group is fixable by a version bump. For tools already at their
latest release, the repo's existing fix is to build from source with the pinned
Go (see the `go:` entries in `mise.toml`). That's a separate change, so suggest
it rather than making it.

`just test` only covers the host's architecture. Say which architecture you
tested on; CI covers the other one.

## 6. Commit

Commit everything as one commit, in the format of the previous bump commit:
list the `mise.toml` versions, then mise (with new checksums), LazyVim, Trivy,
the workflow just version, and the plugin lockfile refresh, whichever apply.

If git has no identity configured, don't change the git config. Commit with
the author of the previous bump commit for this commit only:
`git -c user.name="..." -c user.email="..." commit`.

## 7. Report

Summarize for the user:
- every version that changed, with old → new
- what was checked and already current (base image, apt, pip, npm)
- anything newer that you deliberately left alone, and why
- the test and scan results, with the scan findings grouped by where they come from
- the branch and commit

Then ask whether to push the branch and open a PR.
