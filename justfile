# CI tasks for the personal devcontainer image.
# Override the image name or tag with e.g. `just tag=2026.10.10 push`.

image := env("IMAGE", "vandiver247/personal-devcon")
tag := env("TAG", "latest")
local_ref := image + ":" + tag
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
    tree-sitter --version
    # LazyVim must load without errors and report its version
    lazyvim="$(nvim --headless "+lua io.stdout:write(require('lazyvim.config').version)" +qa)"
    [[ -n "$lazyvim" ]] || { echo "LazyVim failed to load" >&2; exit 1; }
    echo "LazyVim $lazyvim"
    EOF
    echo "all checks passed for {{ local_ref }}"

# Build, test, then push to Docker Hub (needs a `docker login` with push access)
push: test
    docker push {{ local_ref }}

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

# Report pinned tools that have newer versions available (needs mise on the host)
outdated:
    @python3 scripts/outdated_report.py

# Full CI pipeline: build, test, push
ci: push
