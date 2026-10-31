"""Event studies. They measure what prices did around past dates. They do not establish cause."""

import numpy as np
import pandas as pd
from scipy.special import stdtr


class StudyError(ValueError):
    pass


def locate(index: pd.DatetimeIndex, day: str) -> int | None:
    """First trading day on or after the event, because events often land on closed markets."""
    at = index.searchsorted(pd.Timestamp(day))
    return int(at) if at < len(index) else None


def one_event(returns: pd.Series, bench: pd.Series | None, day: str, before: int, after: int, estimation: int, gap: int) -> dict | None:
    at = locate(returns.index, day)
    if at is None or at - before < 0 or at + after >= len(returns):
        return None
    start = at - before - gap - estimation
    alpha, beta = 0.0, 0.0
    if bench is not None and start >= 0:
        y = returns.iloc[start:start + estimation]
        x = bench.reindex(y.index).fillna(0).to_numpy()
        beta, alpha = np.polyfit(x, y.to_numpy(), 1)
    elif bench is not None:
        return None
    window = returns.iloc[at - before:at + after + 1]
    expected = alpha + beta * (bench.reindex(window.index).fillna(0) if bench is not None else 0)
    abnormal = (window - expected).to_numpy()
    return {"date": returns.index[at].strftime("%Y-%m-%d"), "requested": day, "beta": float(beta), "raw_return": float((1 + window).prod() - 1), "car": float(abnormal.sum()), "path": np.cumsum(abnormal).tolist()}


def study(prices: pd.Series, dates: list[str], benchmark: pd.Series | None = None, before: int = 5, after: int = 10, estimation: int = 120, gap: int = 10) -> dict:
    """Abnormal return is the return minus what a pre-event market model expected.

    Without a benchmark, as for commodities, the raw return is used.
    """
    if before < 0 or after < 1:
        raise StudyError("The window must include days after the event.")
    returns = prices.pct_change(fill_method=None).dropna()
    bench = benchmark.pct_change(fill_method=None).dropna() if benchmark is not None else None
    if bench is not None:
        common = returns.index.intersection(bench.index)
        returns, bench = returns.loc[common], bench.loc[common]
    rows = [r for d in dates if (r := one_event(returns, bench, d, before, after, estimation, gap))]
    skipped = [d for d in dates if d not in {r["requested"] for r in rows}]
    cars = np.array([r["car"] for r in rows])
    n = len(cars)
    t_stat = p_value = None
    if n >= 3 and cars.std(ddof=1) > 0:
        t_stat = float(cars.mean() / (cars.std(ddof=1) / np.sqrt(n)))
        p_value = float(2 * stdtr(n - 1, -abs(t_stat)))
    paths = np.array([r["path"] for r in rows]) if rows else np.empty((0, 0))
    return {"n": n, "skipped": skipped, "before": before, "after": after, "market_adjusted": benchmark is not None, "mean_car": float(cars.mean()) if n else None, "median_car": float(np.median(cars)) if n else None, "positive": int((cars > 0).sum()),
            "t_stat": t_stat, "p_value": p_value, "events": [{k: v for k, v in r.items() if k != "path"} for r in rows],
            "mean_path": [{"day": i - before, "value": float(v)} for i, v in enumerate(paths.mean(axis=0))] if n else []}


def benjamini_hochberg(p_values: list[float | None], q: float = 0.1) -> list[bool]:
    """Marks results that survive testing many assets at once. Missing p-values never pass."""
    known = sorted((p, i) for i, p in enumerate(p_values) if p is not None)
    passed = [False] * len(p_values)
    m = len(known)
    cutoff = max((rank for rank, (p, _) in enumerate(known, 1) if p <= q * rank / m), default=0)
    for _p, i in known[:cutoff]:
        passed[i] = True
    return passed
