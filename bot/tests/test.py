import asyncio

from dydx_v4_client import Order
from functions.func_connections import connect_dydx
from functions.func_private import place_market_order


async def main():
    client = await connect_dydx()
    order = await place_market_order(client, "MATIC-USD", "BUY", 10, 0, False)


asyncio.run(main())
