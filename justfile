# CI tasks for the personal devcontainer image.
# Override the image name or tag with e.g. `just tag=2026.10.10 push`.

image := env("IMAGE", "vandiver247/personal-devcon")
tag := env("TAG", "latest")
local_ref := image + ":" + tag
# `push` publishes this machine's build as `<tag>-<arch>`; `manifest` joins the two into `<tag>`.
docker_arch := if arch() == "aarch64" { "arm64" } else { "amd64" }
arch_ref := local_ref + "-" + docker_arch
# With GITHUB_TOKEN set, mise authenticates its GitHub API calls during the build.
build_secret := if env("GITHUB_TOKEN", "") != "" { "--secret id=github_token,env=GITHUB_TOKEN" } else { "" }
trivy_image := "aquasec/trivy:0.75.0@sha256:af6acf9a6b85dfe389a1941505c0ce9efef52a4719635e1a962f022a3d855daa"

# List available recipes
default:
    @just --list

# Build the image
build:
    docker build {{ build_secret }} --tag {{ local_ref }} .

# Build the image, then check that every pinned tool is installed and runs
test: build
    #!/usr/bin/env bash
    set -euo pipefail
    docker run --rm --interactive {{ local_ref }} bash -euo pipefail -s <<'EOF'
    missing="$(mise ls --missing)"
    if [[ -n "$missing" ]]; then
        echo "tools pinned in mise.toml but not installed:" >&2
        echo "$missing" >&2
        exit 1
    fi
    mise ls --current
    just --version
    go version
    python --version
    uv --version
    node --version
    npm --version
    nvim --version | head -n 1
    k3d version
    kubectl version --client
    helm version --short
    k9s version --short
    aws --version
    gh --version
    claude --version
    docker --version
    docker buildx version
    docker compose version
    rg --version | head -n 1
    fd --version
    fzf --version
    lazygit --version
    shfmt --version
    docz version
    tree-sitter --version
    # LazyVim must load without errors and report its version
    lazyvim="$(nvim --headless "+lua io.stdout:write(require('lazyvim.config').version)" +qa)"
    [[ -n "$lazyvim" ]] || { echo "LazyVim failed to load" >&2; exit 1; }
    echo "LazyVim $lazyvim"
    EOF
    echo "all checks passed for {{ local_ref }}"

# Build, test, then push this machine's architecture to Docker Hub as `<tag>-<arch>` (needs a `docker login` with push access)
push: test
    docker tag {{ local_ref }} {{ arch_ref }}
    docker push {{ arch_ref }}

# Join the pushed `<tag>-amd64` and `<tag>-arm64` images into the multi-arch `<tag>`, then check it lists both
manifest:
    #!/usr/bin/env bash
    set -euo pipefail
    docker buildx imagetools create --tag {{ local_ref }} {{ local_ref }}-amd64 {{ local_ref }}-arm64
    platforms="$(docker buildx imagetools inspect {{ local_ref }} | grep -oP 'Platform:\s+\Klinux/\S+' | sort | xargs)"
    if [[ "$platforms" != "linux/amd64 linux/arm64" ]]; then
        echo "{{ local_ref }} should list linux/amd64 and linux/arm64, but lists: ${platforms:-nothing}" >&2
        exit 1
    fi
    echo "{{ local_ref }} is published for $platforms"

# Build the image, then scan it with Trivy; fails on any critical, or any high with a fix available
scan: build
    #!/usr/bin/env bash
    set -euo pipefail
    docker run --rm \
        --volume /var/run/docker.sock:/var/run/docker.sock \
        --volume trivy-cache:/root/.cache/ \
        {{ trivy_image }} image --scanners vuln --format json --quiet {{ local_ref }} \
        > trivy-results.json
    python3 scripts/trivy_report.py trivy-results.json --output trivy-report.md

# Report pinned tools that have newer versions available (needs mise on the host).
# The Neovim plugin check runs in the image: `just build` first to check this checkout.
outdated:
    @python3 scripts/outdated_report.py --image {{ local_ref }}

# Full CI pipeline for one architecture: build, test, push
ci: push
