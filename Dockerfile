# syntax=docker/dockerfile:1
FROM ubuntu:26.04

ARG MISE_VERSION=2026.10.7
ARG MISE_SHA256_AMD64=6eb1b890e90818417ca34c90dbbd47881917d5cd199f31b63b062ea9c6b18d85
ARG MISE_SHA256_ARM64=c7108d85a32ba17e4747d31d4a42f39f0c134f16211e204e8ef0a49d4f518fe1
# LazyVim/starter has no tags, so pin the commit.
ARG LAZYVIM_STARTER_COMMIT=803bc181d7c0d6d5eeba9274d9be49b287294d99
ARG USERNAME=ubuntu
ARG TARGETARCH

SHELL ["/bin/bash", "-euo", "pipefail", "-c"]

# OS-level prerequisites only; every dev tool below is installed by mise.
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        build-essential \
        ca-certificates \
        curl \
        git \
        less \
        locales \
        openssh-client \
        sudo \
        unzip \
        xz-utils \
    && locale-gen en_US.UTF-8 \
    && echo "${USERNAME} ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/${USERNAME} \
    && chmod 0440 /etc/sudoers.d/${USERNAME} \
    && rm -rf /var/lib/apt/lists/*

ENV LANG=en_US.UTF-8 \
    LC_ALL=en_US.UTF-8

# mise is the one tool that can't install itself: fetch the pinned release binary.
RUN case "${TARGETARCH}" in \
        amd64) arch=x64; sha="${MISE_SHA256_AMD64}" ;; \
        arm64) arch=arm64; sha="${MISE_SHA256_ARM64}" ;; \
        *) echo "unsupported architecture: ${TARGETARCH}" >&2; exit 1 ;; \
    esac \
    && curl -fsSL -o /usr/local/bin/mise \
        "https://github.com/jdx/mise/releases/download/v${MISE_VERSION}/mise-v${MISE_VERSION}-linux-${arch}" \
    && echo "${sha}  /usr/local/bin/mise" | sha256sum -c - \
    && chmod 0755 /usr/local/bin/mise

USER ${USERNAME}
WORKDIR /home/${USERNAME}

ENV PATH=/home/${USERNAME}/.local/share/mise/shims:/home/${USERNAME}/.local/bin:${PATH} \
    EDITOR=nvim

# Every dev tool (languages, kubernetes, cloud and docker clients, neovim and
# the LazyVim dependencies) is pinned in mise.toml.
# Pass `--secret id=github_token,env=GITHUB_TOKEN` to avoid GitHub API rate limits.
COPY --chown=${USERNAME}:${USERNAME} mise.toml .config/mise/config.toml
RUN --mount=type=secret,id=github_token,env=GITHUB_TOKEN \
    mise install --yes \
    && mise reshim \
    && mise cache clear \
    && mkdir -p ~/.docker/cli-plugins \
    && ln -s "$(mise where github:docker/buildx)"/buildx-* ~/.docker/cli-plugins/docker-buildx \
    && ln -s "$(mise which docker-compose)" ~/.docker/cli-plugins/docker-compose \
    && echo 'eval "$(mise activate bash)"' >> ~/.bashrc

# LazyVim: pinned starter config, pinned LazyVim release, plugins restored from lazy-lock.json.
RUN git init -q .config/nvim \
    && git -C .config/nvim fetch -q --depth 1 https://github.com/LazyVim/starter.git "${LAZYVIM_STARTER_COMMIT}" \
    && git -C .config/nvim checkout -q FETCH_HEAD \
    && rm -rf .config/nvim/.git
COPY --chown=${USERNAME}:${USERNAME} nvim/lazyvim-pin.lua .config/nvim/lua/plugins/lazyvim-pin.lua
COPY --chown=${USERNAME}:${USERNAME} nvim/lazy-lock.json .config/nvim/lazy-lock.json
RUN nvim --headless "+Lazy! restore" +qa

CMD ["bash"]
