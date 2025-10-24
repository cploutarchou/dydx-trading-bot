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
import argparse
import asyncio
import logging
import random
import sys
import time
from pathlib import Path

# Make the app/ directory importable the same way other scripts do
repo_root = Path(__file__).resolve().parents[1]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from dydx_v4_client import (  # noqa: E402
    MAX_CLIENT_ID,
    NodeClient,
    Order,
    OrderFlags,
    Wallet,
)
from dydx_v4_client.indexer.rest.constants import OrderType  # noqa: E402
from dydx_v4_client.indexer.rest.indexer_client import IndexerClient  # noqa: E402
from dydx_v4_client.network import TESTNET  # noqa: E402
from dydx_v4_client.node.market import Market  # noqa: E402

from backend.app.config import config as app_config  # noqa: E402
from backend.app.constants import INDEXER_ACCOUNT_ENDPOINT  # noqa: E402
from backend.app.func_utils import format_number  # noqa: E402
from backend.app.logging_setup import setup_logging  # noqa: E402

setup_logging()
logger = logging.getLogger(__name__)


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
    if cfg is None:
        logger.error("Configuration could not be loaded; aborting")
        return
    # Get mnemonic from config depending on network
    if cfg.is_testnet:
        if cfg.dydx_testnet is None:
            logger.error("Testnet configuration missing dydx_testnet block; aborting")
            return
        mnemonic = cfg.dydx_testnet.dydx_chain_secret
        cfg_address = cfg.dydx_testnet.dydx_chain_address
    else:
        if cfg.dydx_mainnet is None:
            logger.error("Mainnet configuration missing dydx_mainnet block; aborting")
            return
        mnemonic = cfg.dydx_mainnet.dydx_chain_secret
        cfg_address = cfg.dydx_mainnet.dydx_chain_address

    logger.info("Deriving address from mnemonic...")
    # Derive wallet address
    node = await NodeClient.connect(TESTNET.node)
    wallet = await Wallet.from_mnemonic(node, mnemonic, cfg_address)
    derived_address = wallet.address
    logger.info("Configured address: %s", cfg_address)
    logger.info("Derived address:   %s", derived_address)

    # Prefer derived address if it differs
    if derived_address != cfg_address:
        logger.warning(
            "Address mismatch detected. Using derived address to query indexer and close positions."
        )
        address_to_use = derived_address
    else:
        address_to_use = cfg_address

    # Connect indexer/node/wallet using address_to_use
    indexer, node, wallet = await connect_for_script(INDEXER_ACCOUNT_ENDPOINT, mnemonic, address_to_use)

    found = []  # list of tuples (subaccount, open_positions dict)
    logger.info(
        "Scanning up to %d subaccounts for address %s...",
        args.max_subaccounts,
        address_to_use,
    )
    for subacct in range(0, args.max_subaccounts):
        try:
            resp = await indexer.account.get_subaccount(address_to_use, subacct)
        except Exception as e:
            # likely 404 — no subaccount at this index
            logger.debug("subaccount %d: not found (%s)", subacct, e)
            continue
        sub = resp.get("subaccount", {})
        positions = sub.get("openPerpetualPositions", {})
        if positions and len(positions) > 0:
            found.append((subacct, positions))

    if not found:
        logger.info("No open positions found across scanned subaccounts.")
        return

    # Summarize
    total_positions = sum(len(p) for _, p in found)
    logger.info(
        "Found positions in %d subaccounts (total %d positions):",
        len(found),
        total_positions,
    )
    for subacct, positions in found:
        logger.info(" subaccount %d: %d positions", subacct, len(positions))
        for token, pos in positions.items():
            logger.info(
                "  - %s side=%s size=%s entry=%s",
                pos["market"],
                pos["side"],
                pos["sumOpen"],
                pos.get("entryPrice"),
            )

    if args.dry_run:
        logger.info(
            "Dry-run mode: no orders will be placed. Use without --dry-run to actually close positions."
        )
        return

    # Confirm if not auto-yes
    if not args.y:
        logger.info("Awaiting user confirmation to close positions...")
        confirm = input("Close all found positions? Type 'yes' to proceed: ")
        if confirm.strip().lower() != "yes":
            logger.info("Aborting — no orders placed.")
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

            logger.info(
                "Placing reduce-only market order to close %s (subaccount %d): side %s, size %s, price %s",
                market,
                subacct,
                side,
                size,
                accept_price,
            )
            try:
                order = await node.place_order(
                    wallet,
                    market_obj.order(
                        market_order_id,
                        order_type=OrderType.MARKET,  # type: ignore[arg-type]
                        side=Order.Side.SIDE_BUY if side == "BUY" else Order.Side.SIDE_SELL,
                        size=float(size),
                        price=float(accept_price),  # type: ignore[arg-type]
                        time_in_force=Order.TIME_IN_FORCE_UNSPECIFIED,
                        reduce_only=True,
                        good_til_block=good_til_block,
                    ),
                )
                logger.debug("Close order response: %s", order)
                # brief wait
                time.sleep(1.5)
            except Exception as e:
                logger.error(
                    "Failed to place close order for %s on subaccount %d: %s",
                    market,
                    subacct,
                    e,
                )

    logger.info("Done attempting to close positions.")


if __name__ == "__main__":
    asyncio.run(main())
