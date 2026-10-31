"""Public crypto market and chain data. Addresses are never attributed to people."""

import asyncio

from atlas.core.errors import SourceUnavailable
from atlas.core.fetcher import get_fetcher

RPC = "https://ethereum-rpc.publicnode.com"


async def markets(limit: int = 50) -> dict:
    got = await get_fetcher().get("coingecko", "https://api.coingecko.com/api/v3/coins/markets", params={
        "vs_currency": "usd", "order": "market_cap_desc", "per_page": limit, "page": 1,
        "price_change_percentage": "24h,7d,30d"}, ttl=180)
    rows = [{"id": c["id"], "symbol": c["symbol"].upper(), "name": c["name"], "price": c["current_price"], "market_cap": c["market_cap"],
             "volume_24h": c["total_volume"], "chg_24h": c.get("price_change_percentage_24h_in_currency"),
             "chg_7d": c.get("price_change_percentage_7d_in_currency"), "chg_30d": c.get("price_change_percentage_30d_in_currency"),
             "last_updated": c.get("last_updated")} for c in got.json()]
    return {"coins": rows, "_fetched": got.fetched_at, "_stale": got.stale}


LIVE_PAIRS = {"BTCUSDT": "Bitcoin", "ETHUSDT": "Ethereum", "SOLUSDT": "Solana", "XRPUSDT": "XRP", "BNBUSDT": "BNB", "DOGEUSDT": "Dogecoin"}


async def live_tickers() -> dict:
    """Binance public market data. Priced in USDT, which is close to but not exactly US dollars."""
    pairs = "[" + ",".join(f'"{p}"' for p in LIVE_PAIRS) + "]"
    got = await get_fetcher().get("binance", "https://data-api.binance.vision/api/v3/ticker/24hr", params={"symbols": pairs}, ttl=5)
    rows = [{"symbol": r["symbol"].removesuffix("USDT"), "name": LIVE_PAIRS[r["symbol"]], "price": float(r["lastPrice"]), "change_pct": float(r["priceChangePercent"]), "volume_quote": float(r["quoteVolume"])} for r in got.json()]
    return {"rows": rows, "_fetched": got.fetched_at, "_stale": got.stale}


async def fear_greed() -> dict:
    got = await get_fetcher().get("feargreed", "https://api.alternative.me/fng/", params={"limit": 1}, ttl=3600)
    row = got.json()["data"][0]
    return {"value": int(row["value"]), "label": row["value_classification"]}


async def bitcoin_network() -> dict:
    base = "https://mempool.space/api"
    f = get_fetcher()
    height, fees, pool, hash_ = await asyncio.gather(
        f.get("mempool", f"{base}/blocks/tip/height", ttl=120), f.get("mempool", f"{base}/v1/fees/recommended", ttl=120),
        f.get("mempool", f"{base}/mempool", ttl=120), f.get("mempool", f"{base}/v1/mining/hashrate/3m", ttl=3600))
    hr = hash_.json()
    return {"height": int(height.body), "fees_sat_vb": fees.json(), "mempool_tx": pool.json().get("count"),
            "mempool_vsize": pool.json().get("vsize"), "hashrate_ehs": hr["currentHashrate"] / 1e18, "difficulty": hr["currentDifficulty"],
            "hashrate_history": [{"time": p["timestamp"], "ehs": p["avgHashrate"] / 1e18} for p in hr.get("hashrates", [])],
            "_fetched": height.fetched_at, "_stale": height.stale}


async def _rpc(method: str, params: list, ttl: int = 60):
    got = await get_fetcher().get("ethrpc", RPC, method="POST", ttl=ttl, json_body={"jsonrpc": "2.0", "id": 1, "method": method, "params": params})
    payload = got.json()
    if "error" in payload:
        raise SourceUnavailable("ethrpc", str(payload["error"]))
    return payload["result"]


async def ethereum_network() -> dict:
    head = await _rpc("eth_getBlockByNumber", ["latest", False])
    gas = int(await _rpc("eth_gasPrice", []), 16)
    used, limit = int(head["gasUsed"], 16), int(head["gasLimit"], 16)
    base_fee = int(head.get("baseFeePerGas", "0x0"), 16)
    return {"height": int(head["number"], 16), "timestamp": int(head["timestamp"], 16), "tx_count": len(head["transactions"]),
            "gas_price_gwei": gas / 1e9, "base_fee_gwei": base_fee / 1e9, "gas_utilisation": used / limit}


async def defi() -> dict:
    f = get_fetcher()
    chains, stables = await asyncio.gather(f.get("defillama", "https://api.llama.fi/v2/chains", ttl=3600),
                                           f.get("defillama", "https://stablecoins.llama.fi/stablecoins", params={"includePrices": "false"}, ttl=3600))
    top = sorted(chains.json(), key=lambda c: c.get("tvl") or 0, reverse=True)[:12]
    rows = []
    for a in stables.json()["peggedAssets"]:
        supply = (a.get("circulating") or {}).get("peggedUSD")
        if supply:
            prev = (a.get("circulatingPrevMonth") or {}).get("peggedUSD")
            rows.append({"name": a["name"], "symbol": a["symbol"], "supply_usd": supply, "chg_30d": supply / prev - 1 if prev else None})
    rows.sort(key=lambda r: r["supply_usd"], reverse=True)
    return {"chains": [{"name": c["name"], "tvl": c["tvl"]} for c in top], "stablecoins": rows[:12],
            "stablecoin_total": sum(r["supply_usd"] for r in rows), "_fetched": chains.fetched_at, "_stale": chains.stale}
