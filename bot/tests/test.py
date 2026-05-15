import asyncio

from src.trading.account_manager import place_market_order
from src.trading.dydx_client import connect_dydx


async def main():
    client = await connect_dydx()
    await place_market_order(client, "MATIC-USD", "BUY", 10, 0, False)


asyncio.run(main())
