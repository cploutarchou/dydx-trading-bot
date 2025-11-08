"""
Manual trading test script (NOT A UNIT TEST - requires dYdX connection)

This file is NOT run by pytest. It's a standalone script for manual testing.
Use with: python app/manual_trading_test.py
"""

import asyncio

from func_connections import connect_dydx
from func_private import place_market_order


async def main():
    client = await connect_dydx()
    order = await place_market_order(client, "MATIC-USD", "BUY", 10, 0, False)


if __name__ == "__main__":
    print("⚠️  This is a manual test script, not a unit test")
    print("It requires an active dYdX connection")
    asyncio.run(main())
