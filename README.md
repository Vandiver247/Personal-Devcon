# Personal-Devcon

A personal development container image built on Ubuntu 26.04, published for
`linux/amd64` and `linux/arm64` (Apple silicon). Every tool is pinned to an
exact version, and nearly all of them are installed and managed by
[mise](https://mise.jdx.dev).

## What's inside

| Category | Tools |
|---|---|
| Languages | go, python (with [uv](https://docs.astral.sh/uv/)), node (with npm) |
| Task running | just, mise |
| Editor | neovim with [LazyVim](https://www.lazyvim.org) (plus ripgrep, fd, fzf, lazygit, tree-sitter) |
| Kubernetes | k3d, kubectl, helm, k9s |
| Cloud and SCM | aws-cli, gh |
| Docs | [docz](https://github.com/donaldgifford/docz) |
| AI | Claude Code (`claude`) |
| Containers | docker CLI, buildx, compose (client only) |

Exact versions live in [`mise.toml`](mise.toml).

## Usage

Requires Docker and [just](https://just.systems) on the host.

```sh
just build   # build vandiver247/personal-devcon:latest
just test    # build, then verify every pinned tool is installed and runs
just push    # build, test, then push this machine's architecture as latest-amd64 or latest-arm64
just manifest  # join latest-amd64 and latest-arm64 into the multi-arch latest, then verify it
just scan    # build, then scan the image with Trivy
just outdated  # report pinned tools, Neovim plugins and the Ubuntu LTS that have newer versions (needs mise and python3)
```

The image is published to Docker Hub as
[`vandiver247/personal-devcon`](https://hub.docker.com/r/vandiver247/personal-devcon).
`just push` and `just manifest` need a `docker login` session with push access
to that repository. Override the image name or tag with
`just image=foo/bar tag=1.2.3 push` or the `IMAGE` / `TAG` environment variables.

`just build` always builds for the machine it runs on, so each architecture is
built and tested natively, never under emulation. `just push` publishes that
build under an architecture-suffixed tag, and `just manifest` points the plain
tag at both, so `docker pull` picks the right one. Publishing by hand therefore
takes `just push` on an amd64 machine, `just push` on an arm64 machine, then
`just manifest` on either.

Run the container:

```sh
docker run -it vandiver247/personal-devcon:latest
```

The image ships only the Docker client. To use `docker` or `k3d` inside the
container, mount the host's Docker socket and add its group:

```sh
docker run -it \
  -v /var/run/docker.sock:/var/run/docker.sock \
  --group-add "$(stat -c %g /var/run/docker.sock)" \
  vandiver247/personal-devcon:latest
```

The container runs as the `ubuntu` user (UID 1000) with passwordless sudo.

### VS Code

This repo has a [dev container configuration](.devcontainer/devcontainer.json)
that opens it inside `vandiver247/personal-devcon:latest`. With the
[Dev Containers extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers)
installed, run **Dev Containers: Reopen in Container**.

Docker reuses a locally cached `latest`, so run
`docker pull vandiver247/personal-devcon:latest` and then
**Dev Containers: Rebuild Container** to pick up a newly published image.

## Where versions are pinned

| What | Where |
|---|---|
| Tools installed by mise | [`mise.toml`](mise.toml) |
| Ubuntu, mise itself, LazyVim starter commit | `ARG`s at the top of the [`Dockerfile`](Dockerfile) |
| LazyVim release | [`nvim/lazyvim-pin.lua`](nvim/lazyvim-pin.lua) |
| Neovim plugin commits | [`nvim/lazy-lock.json`](nvim/lazy-lock.json) |
| GitHub Actions used by the workflows | Commit SHAs in [`.github/workflows/`](.github/workflows), bumped by [Dependabot](.github/dependabot.yml) pull requests |

To upgrade a tool, bump its version and run `just test`. When bumping mise,
update both `MISE_SHA256_*` values from that release's `SHASUMS256.txt`. To
refresh the plugin lockfile, run `nvim --headless "+Lazy! sync" +qa` in the
container and copy `~/.config/nvim/lazy-lock.json` back to `nvim/`.

The apt prerequisites (git, curl, build-essential and similar) are not pinned.

## CI

| Workflow | Trigger | What it does |
|---|---|---|
| [CI](.github/workflows/ci.yml) | Pull request to `main` | `just test` on a native amd64 runner and a native arm64 runner |
| [Version report](.github/workflows/version-report.yml) | Pull request to `main` | Comments on the PR with any pinned tools, Neovim plugins (lazy.nvim's own check, run in the built image) or Ubuntu LTS release that have newer versions. Informational, not a merge gate |
| [Security](.github/workflows/security.yml) | Pull request to `main` | `just scan`: Trivy scan of the built image, posted as a PR comment. Fails on any critical finding, or any high finding with a fix available. Scans the amd64 image only |
| [Publish](.github/workflows/publish.yml) | Push to `main` (including merged PRs) that changes the image: `Dockerfile`, `.dockerignore`, `mise.toml` or `nvim/` | `just push` on a native runner for each architecture, then `just manifest` to update the multi-arch `latest` on Docker Hub. If either architecture fails its build or test, `latest` is left untouched |
| [Scheduled build](.github/workflows/scheduled-build.yml) | Every Monday at 06:00 UTC, or manually | Rebuilds from scratch to pick up base image and apt updates, and republishes the same way as Publish: both architectures must pass `just test` before `latest` is updated. Also runs `just scan` on each architecture and adds the Trivy report to the run summary, but findings do not block the publish |

The Publish and Scheduled build workflows need two secrets, stored in the
`dockerhub` [environment](https://docs.github.com/actions/deployment/targeting-different-environments)
rather than at the repository level. The environment only accepts runs from
`main`, so a workflow on any other branch or in a pull request cannot read them.

- `DOCKERHUB_USERNAME`: your Docker Hub username
- `DOCKERHUB_TOKEN`: a Docker Hub access token with read and write access

Set them with `gh secret set --env dockerhub DOCKERHUB_USERNAME` and
`gh secret set --env dockerhub DOCKERHUB_TOKEN`.
