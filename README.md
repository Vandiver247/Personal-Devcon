# Personal-Devcon

A personal development container image built on Ubuntu 26.04. Every tool is
pinned to an exact version, and nearly all of them are installed and managed by
[mise](https://mise.jdx.dev).

## What's inside

| Category | Tools |
|---|---|
| Languages | go, python |
| Task running | just, mise |
| Editor | neovim with [LazyVim](https://www.lazyvim.org) (plus ripgrep, fd, fzf, lazygit, tree-sitter) |
| Kubernetes | k3d, kubectl, helm, k9s |
| Cloud and SCM | aws-cli, gh |
| Containers | docker CLI, buildx, compose (client only) |

Exact versions live in [`mise.toml`](mise.toml).

## Usage

Requires Docker and [just](https://just.systems) on the host.

```sh
just build   # build personal-devcon:latest
just test    # build, then verify every pinned tool is installed and runs
just push    # build, test, then push to Docker Hub as <logged-in-user>/personal-devcon
```

`just push` reads the Docker Hub username from your `docker login` session and
needs `jq`. Override the image name or tag with `just image=foo tag=1.2.3 push`
or the `IMAGE` / `TAG` environment variables.

Run the container:

```sh
docker run -it personal-devcon:latest
```

The image ships only the Docker client. To use `docker` or `k3d` inside the
container, mount the host's Docker socket and add its group:

```sh
docker run -it \
  -v /var/run/docker.sock:/var/run/docker.sock \
  --group-add "$(stat -c %g /var/run/docker.sock)" \
  personal-devcon:latest
```

The container runs as the `ubuntu` user (UID 1000) with passwordless sudo.

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
| [Publish](.github/workflows/publish.yml) | Push to `main` (including merged PRs) | `just push` to Docker Hub |

The Publish workflow needs two repository secrets:

- `DOCKERHUB_USERNAME`: your Docker Hub username
- `DOCKERHUB_TOKEN`: a Docker Hub access token with write access

Set them with `gh secret set DOCKERHUB_USERNAME` and `gh secret set DOCKERHUB_TOKEN`.
