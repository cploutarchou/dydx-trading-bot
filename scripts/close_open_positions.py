#!/usr/bin/env python3
"""Close open perpetual positions for the address derived from the configured mnemonic.

This script:
- Loads YAML config via app.config
- Derives the on-chain address from the mnemonic
- Queries the indexer for open positions for that address (subaccount 0)
- For each open position, places a market reduce-only order to close it

Run inside the project's venv:
. .venv/bin/activate
python scripts/close_open_positions.py
"""
import asyncio
import random
import sys
import time
from pathlib import Path
from pprint import pprint

# Make the app/ directory importable the same way other scripts do
repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root / "app"))

import argparse

from config import config as app_config
from constants import INDEXER_ACCOUNT_ENDPOINT
from dydx_v4_client import MAX_CLIENT_ID, NodeClient, Order, OrderFlags, Wallet
from dydx_v4_client.indexer.rest.constants import OrderType
from dydx_v4_client.indexer.rest.indexer_client import IndexerClient
from dydx_v4_client.network import TESTNET
from dydx_v4_client.node.market import Market
from func_utils import format_number


def parse_args():
    p = argparse.ArgumentParser(
        description="Close open perpetual positions for the address derived from the configured mnemonic."
    )
    p.add_argument("--max-subaccounts", type=int, default=3, help="Max subaccounts to scan (default: 3)")
    p.add_argument("--dry-run", action="store_true", help="Don't place orders; only print what would be done")
    p.add_argument("-y", "--yes", action="store_true", help="Non-interactive: skip confirmation and proceed to place orders")
    return p.parse_args()


async def connect_for_script(indexer_endpoint: str, mnemonic: str, derived_address: str):
    indexer = IndexerClient(host=indexer_endpoint, api_timeout=5)
    node = await NodeClient.connect(TESTNET.node)
    wallet = await Wallet.from_mnemonic(node, mnemonic, derived_address)
    return indexer, node, wallet


async def main():
    args = parse_args()
    cfg = app_config()
    # Get mnemonic from config depending on network
    if cfg.is_testnet:
        mnemonic = cfg.dydx_testnet.dydx_chain_secret
        cfg_address = cfg.dydx_testnet.dydx_chain_address
    else:
        mnemonic = cfg.dydx_mainnet.dydx_chain_secret
        cfg_address = cfg.dydx_mainnet.dydx_chain_address

    print("Deriving address from mnemonic...")
    # Derive wallet address
    node = await NodeClient.connect(TESTNET.node)
    wallet = await Wallet.from_mnemonic(node, mnemonic, cfg_address)
    derived_address = wallet.address
    print("Configured address:", cfg_address)
    print("Derived address:   ", derived_address)

    # Prefer derived address if it differs
    if derived_address != cfg_address:
        print("Address mismatch detected. Using derived address to query indexer and close positions.")
        address_to_use = derived_address
    else:
        address_to_use = cfg_address

    # Connect indexer/node/wallet using address_to_use
    indexer, node, wallet = await connect_for_script(INDEXER_ACCOUNT_ENDPOINT, mnemonic, address_to_use)

    found = []  # list of tuples (subaccount, open_positions dict)
    print(f"Scanning up to {args.max_subaccounts} subaccounts for address {address_to_use}...")
    for subacct in range(0, args.max_subaccounts):
        try:
            resp = await indexer.account.get_subaccount(address_to_use, subacct)
        except Exception as e:
            # likely 404 — no subaccount at this index
            print(f"subaccount {subacct}: not found ({e})")
            continue
        sub = resp.get("subaccount", {})
        positions = sub.get("openPerpetualPositions", {})
        if positions and len(positions) > 0:
            found.append((subacct, positions))

    if not found:
        print("No open positions found across scanned subaccounts.")
        return

    # Summarize
    total_positions = sum(len(p) for _, p in found)
    print(f"Found positions in {len(found)} subaccounts (total {total_positions} positions):")
    for subacct, positions in found:
        print(f" subaccount {subacct}: {len(positions)} positions")
        for token, pos in positions.items():
            print(f"  - {pos['market']} side={pos['side']} size={pos['sumOpen']} entry={pos.get('entryPrice')}")

    if args.dry_run:
        print("Dry-run mode: no orders will be placed. Use without --dry-run to actually close positions.")
        return

    # Confirm if not auto-yes
    if not args.y:
        confirm = input("Close all found positions? Type 'yes' to proceed: ")
        if confirm.strip().lower() != "yes":
            print("Aborting — no orders placed.")
            return

    # Fetch markets for tick sizes
    markets_raw = await indexer.markets.get_perpetual_markets()
    markets = markets_raw.get("markets", {})

    # Close each position using a market reduce-only order
    for subacct, positions in found:
        for token, pos in positions.items():
            market = pos["market"]
            side = "BUY" if pos["side"] == "LONG" else "SELL"
            size = pos["sumOpen"]
            price = float(pos.get("entryPrice", 0))
            # Set an aggressive accept price to ensure fill
            accept_price = price * 1.7 if side == "BUY" else price * 0.3
            tick_size = markets[market]["tickSize"]
            accept_price = format_number(accept_price, tick_size)

            # Build market object
            market_obj = Market((await indexer.markets.get_perpetual_markets(market))["markets"][market])

            # Create order id using derived address
            market_order_id = market_obj.order_id(address_to_use, subacct, random.randint(0, MAX_CLIENT_ID), OrderFlags.SHORT_TERM)
            current_block = await node.latest_block_height()
            good_til_block = current_block + 1 + 10

            print(f"Placing reduce-only market order to close {market} (subaccount {subacct}): side {side}, size {size}, price {accept_price}")
            try:
                order = await node.place_order(
                    wallet,
                    market_obj.order(
                        market_order_id,
                        order_type=OrderType.MARKET,
                        side=Order.Side.SIDE_BUY if side == "BUY" else Order.Side.SIDE_SELL,
                        size=float(size),
                        price=float(accept_price),
                        time_in_force=Order.TIME_IN_FORCE_UNSPECIFIED,
                        reduce_only=True,
                        good_til_block=good_til_block,
                    ),
                )
                print("Close order placed, response:")
                pprint(order)
                # brief wait
                time.sleep(1.5)
            except Exception as e:
                print(f"Failed to place close order for {market} on subaccount {subacct}: {e}")

    print("Done attempting to close positions.")


if __name__ == "__main__":
    asyncio.run(main())
