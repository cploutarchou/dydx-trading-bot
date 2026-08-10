"""Report whether the bot devcontainer can reach its required services."""

from __future__ import annotations

import socket


ENDPOINTS = (("postgresql", 5432), ("valkey", 6379))


def main() -> None:
    for host, port in ENDPOINTS:
        try:
            with socket.create_connection((host, port), timeout=30):
                print(f"{host}:{port} reachable")
        except OSError as exc:
            print(f"WARN: {host}:{port} not reachable: {exc}")


if __name__ == "__main__":
    main()
