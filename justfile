# CI tasks for the personal devcontainer image.
# Override the image name or tag with e.g. `just tag=2026.10.10 push`.

image := env("IMAGE", "vandiver247/personal-devcon")
tag := env("TAG", "latest")
local_ref := image + ":" + tag
# With GITHUB_TOKEN set, mise authenticates its GitHub API calls during the build.
build_secret := if env("GITHUB_TOKEN", "") != "" { "--secret id=github_token,env=GITHUB_TOKEN" } else { "" }

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
    docker --version
    docker buildx version
    docker compose version
    rg --version | head -n 1
    fd --version
    fzf --version
    lazygit --version
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

# Full CI pipeline: build, test, push
ci: push
