"""Pure market calculations. No I/O, so every number here can be unit tested."""

import numpy as np
import pandas as pd

TRADING_DAYS = 252


def closes(bars: list[dict]) -> pd.Series:
    s = pd.Series({pd.Timestamp(b["time"], unit="s").normalize(): b["close"] for b in bars}, dtype=float)
    return s[~s.index.duplicated(keep="last")].sort_index().dropna()


def sma(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(n).mean()


def ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False).mean()


def rsi(s: pd.Series, n: int = 14) -> pd.Series:
    delta = s.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    rs = gain / loss.replace(0, np.nan)
    return (100 - 100 / (1 + rs)).where(loss != 0, 100.0)


def macd(s: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    line = ema(s, fast) - ema(s, slow)
    sig = ema(line, signal)
    return pd.DataFrame({"macd": line, "signal": sig, "hist": line - sig})


def bollinger(s: pd.Series, n: int = 20, k: float = 2.0) -> pd.DataFrame:
    mid, sd = s.rolling(n).mean(), s.rolling(n).std()
    return pd.DataFrame({"mid": mid, "upper": mid + k * sd, "lower": mid - k * sd})


def trailing_returns(s: pd.Series) -> dict[str, float | None]:
    out: dict[str, float | None] = {}
    for label, days in (("1W", 5), ("1M", 21), ("3M", 63), ("6M", 126), ("1Y", 252), ("3Y", 756), ("5Y", 1260)):
        out[label] = float(s.iloc[-1] / s.iloc[-1 - days] - 1) if len(s) > days else None
    jan = s[s.index.year == s.index[-1].year] if len(s) else s
    prior = s[s.index.year < s.index[-1].year] if len(s) else s
    out["YTD"] = float(s.iloc[-1] / prior.iloc[-1] - 1) if len(jan) and len(prior) else None
    return out


def realised_vol(s: pd.Series, n: int = 30) -> float | None:
    r = np.log(s).diff().dropna()
    return float(r.tail(n).std() * np.sqrt(TRADING_DAYS)) if len(r) >= n else None


def correlation(frames: dict[str, pd.Series]) -> pd.DataFrame:
    return pd.DataFrame({k: v.pct_change(fill_method=None) for k, v in frames.items()}).dropna(how="all").corr(min_periods=30)


def screen_row(symbol: str, name: str, sector: str, bars: list[dict]) -> dict | None:
    s = closes(bars)
    if len(s) < 30:
        return None
    last = float(s.iloc[-1])
    vols = [b["volume"] for b in bars if b.get("volume")]
    r = trailing_returns(s)
    sma50, sma200 = (float(sma(s, n).iloc[-1]) if len(s) >= n else None for n in (50, 200))
    return {"symbol": symbol, "name": name, "sector": sector, "price": last, "chg_1d": float(s.iloc[-1] / s.iloc[-2] - 1),
            "chg_1m": r["1M"], "chg_3m": r["3M"], "chg_1y": r["1Y"], "ytd": r["YTD"], "vol_30d": realised_vol(s),
            "rsi": float(rsi(s).iloc[-1]), "above_50": last > sma50 if sma50 else None,
            "above_200": last > sma200 if sma200 else None,
            "rel_volume": float(vols[-1] / np.mean(vols[-21:-1])) if len(vols) > 21 else None,
            "pct_from_high": float(last / s.tail(252).max() - 1)}


def breadth(rows: list[dict]) -> dict:
    def share(key):
        vals = [r[key] for r in rows if r.get(key) is not None]
        return sum(vals) / len(vals) if vals else None

    return {"universe": len(rows), "above_50dma": share("above_50"), "above_200dma": share("above_200"),
            "advancers": sum(1 for r in rows if r["chg_1d"] > 0), "decliners": sum(1 for r in rows if r["chg_1d"] < 0)}
