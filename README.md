# Personal-Devcon

A personal development container image built on Ubuntu 26.04. Every tool is
pinned to an exact version, and nearly all of them are installed and managed by
[mise](https://mise.jdx.dev).

## What's inside

| Category | Tools |
|---|---|
| Languages | go, python, node (with npm) |
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
just push    # build, test, then push to Docker Hub
just scan    # build, then scan the image with Trivy
just outdated  # report pinned tools, Neovim plugins and the Ubuntu LTS that have newer versions (needs mise and python3)
```

The image is published to Docker Hub as
[`vandiver247/personal-devcon`](https://hub.docker.com/r/vandiver247/personal-devcon).
`just push` needs a `docker login` session with push access to that repository.
Override the image name or tag with `just image=foo/bar tag=1.2.3 push` or the
`IMAGE` / `TAG` environment variables.

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

To upgrade a tool, bump its version and run `just test`. When bumping mise,
update both `MISE_SHA256_*` values from that release's `SHASUMS256.txt`. To
refresh the plugin lockfile, run `nvim --headless "+Lazy! sync" +qa` in the
container and copy `~/.config/nvim/lazy-lock.json` back to `nvim/`.

The apt prerequisites (git, curl, build-essential and similar) are not pinned.

## CI

| Workflow | Trigger | What it does |
|---|---|---|
| [CI](.github/workflows/ci.yml) | Pull request to `main` | `just test` |
| [Version report](.github/workflows/version-report.yml) | Pull request to `main` | Comments on the PR with any pinned tools, Neovim plugins (lazy.nvim's own check, run in the built image) or Ubuntu LTS release that have newer versions. Informational, not a merge gate |
| [Security](.github/workflows/security.yml) | Pull request to `main` | `just scan`: Trivy scan of the built image, posted as a PR comment. Fails on any critical finding, or any high finding with a fix available |
| [Publish](.github/workflows/publish.yml) | Push to `main` (including merged PRs) that changes the image: `Dockerfile`, `.dockerignore`, `mise.toml` or `nvim/` | `just push` to `vandiver247/personal-devcon` on Docker Hub |
| [Scheduled build](.github/workflows/scheduled-build.yml) | Every Monday at 06:00 UTC, or manually | Rebuilds from scratch to pick up base image and apt updates, runs `just test`, and republishes `latest` if it passes. Also runs `just scan` and adds the Trivy report to the run summary, but findings do not block the publish |

The Publish and Scheduled build workflows need two repository secrets:

- `DOCKERHUB_USERNAME`: your Docker Hub username
- `DOCKERHUB_TOKEN`: a Docker Hub access token with write access

Set them with `gh secret set DOCKERHUB_USERNAME` and `gh secret set DOCKERHUB_TOKEN`.
