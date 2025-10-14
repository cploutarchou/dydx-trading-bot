#!/usr/bin/env python3
"""Request testnet USDC helper

This helper tries to automate requesting testnet USDC for dYdX testnet addresses.
It cannot guarantee funds (faucets change), but it provides:
- Attempts against known public endpoints (if available)
- Curl examples for manual execution
- Guidance and exit codes

Usage:
  python scripts/request_testnet_usdc.py --address <dydx_address> --amount 1000

Note: This script does not hold secrets and does not send private keys. It only
interacts with public faucets or prints instructions that you can run locally.
"""

import argparse
import sys
import webbrowser
from textwrap import dedent

KNOWN_FAUCETS = [
    # public UI pages where users can request testnet funds
    "https://v4.testnet.dydx.exchange/",
    # Add more if known
]


def print_manual_instructions(address: str, amount: float) -> None:
    print(dedent(f"""
    Manual instructions to get testnet USDC for address: {address}

    1) Open the dYdX Testnet page and connect the wallet for '{address}':
       {KNOWN_FAUCETS[0]}

    2) If a "Faucet" or "Get Testnet Funds" button exists, request USDC (example: {amount} USDC).

    3) If no faucet UI exists, try a testnet bridge or faucet for the underlying chain
       (e.g., Sepolia/Goerli ETH faucets + testnet USDC bridges). Example steps:

       # Example: open dYdX testnet in your browser now
       (a) Visit: {KNOWN_FAUCETS[0]}
       (b) Connect your wallet (Metamask / other)
       (c) Use the built-in faucet to request USDC

    4) If you want a curl example for a REST-style faucet (if available), below is a generic template

    curl -X POST "https://example-faucet.testnet/fund" \
      -H 'Content-Type: application/json' \
      -d '{{"address":"{address}", "token":"USDC", "amount":{amount}}}'

    Replace the endpoint above with the faucet endpoint provided by your testnet provider.
    """))


def open_faucet_uis():
    print("Opening known faucet UI pages in your default browser...")
    for url in KNOWN_FAUCETS:
        print(" -", url)
        try:
            webbrowser.open(url)
        except Exception:
            print(f"Could not open browser for {url}; please open it manually.")


def main():
    parser = argparse.ArgumentParser(description="Request testnet USDC helper for dYdX")
    parser.add_argument("--address", required=True, help="dYdX chain address (e.g. dydx1...")
    parser.add_argument("--amount", type=float, default=1000.0, help="Amount of USDC to request (default: 1000)")
    parser.add_argument("--open-ui", action="store_true", help="Try to open known faucet UIs in the browser")
    parser.add_argument("--print-only", action="store_true", help="Only print instructions/curl examples and exit")

    args = parser.parse_args()

    address = args.address
    amount = args.amount

    # Minimal validation
    if not address.startswith("dydx"):
        print("Warning: provided address does not look like a dydx address. Proceeding anyway.")

    print(f"Testnet funding helper — address={address} amount={amount}")

    if args.print_only:
        print_manual_instructions(address, amount)
        sys.exit(0)

    if args.open_ui:
        open_faucet_uis()
        print("Opened faucet UIs. Follow the instructions in your browser to request USDC.")
        sys.exit(0)

    # Best effort: no widely documented public REST faucet for dYdX v4 exists at time of writing
    # Fall back to printing manual instructions and suggested curl template
    print("No public REST faucet is configured in this helper.\nFalling back to manual instructions and curl template.")
    print_manual_instructions(address, amount)

    sys.exit(0)


if __name__ == "__main__":
    main()
