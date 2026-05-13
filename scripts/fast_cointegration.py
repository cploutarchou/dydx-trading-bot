"""Fast cointegration scan for a small set of markets.

Usage:
  python scripts/fast_cointegration.py --n 30

Saves results to app/cointegrated_pairs_fast.csv
"""
import argparse
import asyncio

import pandas as pd
from func_connections import connect_dydx
from func_public import get_candles_recent, get_markets

from backend.app.func_cointegration import calculate_cointegration


async def run(n_markets: int):
    client = await connect_dydx()
    markets_resp = await get_markets(client)
    all_markets = [m for m in markets_resp["markets"].keys() if markets_resp["markets"][m]["status"] == "ACTIVE"]
    selected = all_markets[:n_markets]
    print(f"Selected {len(selected)} markets: {selected}")

    results = []
    for i, base in enumerate(selected[:-1]):
        s1 = await get_candles_recent(client, base)
        for j, quote in enumerate(selected[i+1:], start=i+1):
            try:
                s2 = await get_candles_recent(client, quote)
                if len(s1) == 0 or len(s2) == 0 or len(s1) != len(s2):
                    continue
                coint_flag, hedge_ratio, half_life = calculate_cointegration(s1, s2)
                if coint_flag == 1 and 0 < half_life <= 24:
                    results.append({
                        "base_market": base,
                        "quote_market": quote,
                        "hedge_ratio": hedge_ratio,
                        "half_life": half_life,
                    })
                    print(f"Found pair: {base} / {quote} hl={half_life:.2f}")
            except Exception as e:
                print(f"Skipping {base}/{quote}: {e}")
    df = pd.DataFrame(results)
    out_path = "app/cointegrated_pairs_fast.csv"
    df.to_csv(out_path, index=False)
    print(f"Saved {len(df)} pairs to {out_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=30, help="number of markets to scan")
    args = parser.parse_args()
    asyncio.run(run(args.n))
