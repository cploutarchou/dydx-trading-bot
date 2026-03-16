FROM mcr.microsoft.com/devcontainers/go:1-1.23-bookworm

# The upstream base image currently includes a stale Yarn apt source that causes
# feature installation to fail during apt-get update. Remove it before Features
# are applied so the standard devcontainer feature pipeline can complete.
RUN rm -f /etc/apt/sources.list.d/yarn.list \
    /usr/share/keyrings/yarn-archive-keyring.gpg
