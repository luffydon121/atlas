"""Backtesting and portfolio research. Signals act on the next bar, so a bar cannot trade on itself."""

from collections.abc import Callable
from itertools import product

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from atlas.services.analytics import TRADING_DAYS, rsi, sma


class ResearchError(ValueError):
    pass


def sma_cross(px: pd.Series, fast: int = 50, slow: int = 200) -> pd.Series:
    if fast >= slow:
        return pd.Series(np.nan, index=px.index)
    return (sma(px, fast) > sma(px, slow)).astype(float).where(sma(px, slow).notna())


def momentum(px: pd.Series, lookback: int = 252, skip: int = 21) -> pd.Series:
    return (px.shift(skip) / px.shift(lookback) - 1 > 0).astype(float).where(px.shift(lookback).notna())


def mean_reversion(px: pd.Series, period: int = 14, entry: float = 30, exit: float = 55) -> pd.Series:
    r = rsi(px, period)
    state = pd.Series(np.nan, index=px.index)
    state[r < entry] = 1.0
    state[r > exit] = 0.0
    return state.ffill().fillna(0.0).where(r.notna())


def buy_hold(px: pd.Series) -> pd.Series:
    return pd.Series(1.0, index=px.index)


STRATEGIES: dict[str, tuple[Callable, dict[str, list]]] = {
    "buy_hold": (buy_hold, {}),
    "sma_cross": (sma_cross, {"fast": [20, 50, 100], "slow": [100, 150, 200]}),
    "momentum": (momentum, {"lookback": [126, 189, 252]}),
    "mean_reversion": (mean_reversion, {"period": [7, 14], "entry": [25, 30, 35]}),
}


def metrics(returns: pd.Series) -> dict:
    r = returns.dropna()
    if len(r) < 2:
        return {}
    equity = (1 + r).cumprod()
    years = len(r) / TRADING_DAYS
    downside = r[r < 0].std() * np.sqrt(TRADING_DAYS)
    vol = r.std() * np.sqrt(TRADING_DAYS)
    dd = equity / equity.cummax() - 1
    cagr = equity.iloc[-1] ** (1 / years) - 1 if equity.iloc[-1] > 0 else -1.0
    return {"total_return": float(equity.iloc[-1] - 1), "cagr": float(cagr), "volatility": float(vol),
            "sharpe": float(r.mean() / r.std() * np.sqrt(TRADING_DAYS)) if r.std() > 0 else None,
            "sortino": float(r.mean() * TRADING_DAYS / downside) if downside and downside > 0 else None,
            "max_drawdown": float(dd.min()), "calmar": float(cagr / abs(dd.min())) if dd.min() < 0 else None,
            "hit_rate": float((r > 0).sum() / max((r != 0).sum(), 1)), "bars": int(len(r))}


def simulate(px: pd.Series, signal: pd.Series, cost_bps: float = 10) -> pd.DataFrame:
    """Position is yesterday's signal. Cost applies to turnover at the change of position."""
    position = signal.shift(1).fillna(0.0)
    gross = px.pct_change(fill_method=None).fillna(0.0)
    turnover = position.diff().abs().fillna(position.abs())
    net = position * gross - turnover * cost_bps / 10_000
    return pd.DataFrame({"position": position, "gross": gross, "net": net, "turnover": turnover})


def backtest(px: pd.Series, strategy: str, params: dict | None = None, cost_bps: float = 10) -> dict:
    fn = _strategy(strategy)
    if len(px) < 260:
        raise ResearchError("At least 260 daily bars are needed for a meaningful test.")
    result = simulate(px, fn(px, **(params or {})), cost_bps)
    live = result[result["position"].cumsum() > 0] if result["position"].sum() else result
    start = live.index[0] if len(live) else result.index[0]
    result = result[result.index >= start]
    benchmark = result["gross"]
    entries = int(((result["position"] > 0) & (result["position"].shift(1).fillna(0) == 0)).sum())
    return {"strategy": strategy, "params": params or {}, "cost_bps": cost_bps, "metrics": metrics(result["net"]), "benchmark": metrics(benchmark),
            "trades": entries, "exposure": float(result["position"].mean()), "curve": _curve(result["net"], benchmark)}


def _curve(net: pd.Series, benchmark: pd.Series, points: int = 400) -> list[dict]:
    eq, bm = (1 + net).cumprod(), (1 + benchmark).cumprod()
    step = max(len(eq) // points, 1)
    dd = eq / eq.cummax() - 1
    return [{"date": d.strftime("%Y-%m-%d"), "equity": float(eq.loc[d]), "benchmark": float(bm.loc[d]), "drawdown": float(dd.loc[d])} for d in eq.index[::step]]


def _strategy(name: str) -> Callable:
    if name not in STRATEGIES:
        raise ResearchError(f"Unknown strategy {name}")
    return STRATEGIES[name][0]


def walk_forward(px: pd.Series, strategy: str, cost_bps: float = 10, train: int = 756, test: int = 126) -> dict:
    """Picks parameters on a trailing window only, then trades them on the next unseen window."""
    fn, grid = STRATEGIES.get(strategy, (None, None))
    if fn is None:
        raise ResearchError(f"Unknown strategy {strategy}")
    if len(px) < train + test:
        raise ResearchError(f"Walk-forward needs {train + test} bars, have {len(px)}.")
    combos = [dict(zip(grid, values, strict=True)) for values in product(*grid.values())] or [{}]
    oos, folds = [], []
    for start in range(train, len(px) - test + 1, test):
        best, best_score = combos[0], -np.inf
        for combo in combos:
            hist = px.iloc[:start].iloc[-train:]
            r = simulate(hist, fn(hist, **combo), cost_bps)["net"]
            score = r.mean() / r.std() if r.std() > 0 else -np.inf
            if score > best_score:
                best, best_score = combo, score
        # Signals are computed through the fold end, but `simulate` lags them; only fold bars are scored.
        window = px.iloc[: start + test]
        fold = simulate(window, fn(window, **best), cost_bps)["net"].iloc[start:]
        oos.append(fold)
        folds.append({"from": fold.index[0].strftime("%Y-%m-%d"), "to": fold.index[-1].strftime("%Y-%m-%d"), "params": best,
                      "in_sample_sharpe": float(best_score * np.sqrt(TRADING_DAYS)) if np.isfinite(best_score) else None,
                      "oos_return": float((1 + fold).prod() - 1)})
    joined = pd.concat(oos)
    return {"strategy": strategy, "train_bars": train, "test_bars": test, "folds": folds, "out_of_sample": metrics(joined),
            "benchmark": metrics(px.pct_change(fill_method=None).loc[joined.index]), "curve": _curve(joined, px.pct_change(fill_method=None).loc[joined.index])}


def monte_carlo(returns: pd.Series, horizon: int = 252, paths: int = 2000, block: int = 21, seed: int = 7) -> dict:
    """Block bootstrap of history. It keeps short-run clustering but cannot show regimes not in the sample."""
    r = returns.dropna().to_numpy()
    if len(r) < block * 3:
        raise ResearchError("Not enough return history.")
    rng = np.random.default_rng(seed)
    blocks = horizon // block + 1
    starts = rng.integers(0, len(r) - block, size=(paths, blocks))
    idx = (starts[..., None] + np.arange(block)).reshape(paths, -1)[:, :horizon]
    wealth = np.cumprod(1 + r[idx], axis=1)
    bands = np.percentile(wealth, [5, 25, 50, 75, 95], axis=0)
    step = max(horizon // 60, 1)
    final = wealth[:, -1]
    peak = np.maximum.accumulate(wealth, axis=1)
    return {"horizon": horizon, "paths": paths, "block": block, "prob_loss": float((final < 1).mean()),
            "final_p5": float(np.percentile(final, 5) - 1), "final_p50": float(np.median(final) - 1), "final_p95": float(np.percentile(final, 95) - 1),
            "median_max_drawdown": float(np.median((wealth / peak - 1).min(axis=1))),
            "bands": [{"day": int(i + 1), "p5": float(bands[0, i]), "p25": float(bands[1, i]), "p50": float(bands[2, i]), "p75": float(bands[3, i]), "p95": float(bands[4, i])}
                      for i in range(0, horizon, step)]}


def optimise(prices: pd.DataFrame, objective: str = "max_sharpe", rf: float = 0.04, max_weight: float = 1.0) -> dict:
    """Long-only optimiser on historical moments. Expected returns are noisy; treat as exploratory."""
    r = prices.pct_change(fill_method=None).dropna()
    if len(r) < 120 or r.shape[1] < 2:
        raise ResearchError("Need at least two assets and 120 overlapping bars.")
    mu, cov = r.mean().to_numpy() * TRADING_DAYS, r.cov().to_numpy() * TRADING_DAYS
    n = len(mu)
    if max_weight * n < 1:
        raise ResearchError("Maximum weight is too low for the number of assets.")

    def port(w):
        return float(w @ mu), float(np.sqrt(w @ cov @ w))

    def risk_parity(w):
        total = w @ cov @ w
        contrib = w * (cov @ w)
        return float(((contrib - total / n) ** 2).sum() * 1e3)

    objectives = {"max_sharpe": lambda w: -(port(w)[0] - rf) / port(w)[1], "min_variance": lambda w: port(w)[1], "risk_parity": risk_parity}
    if objective not in objectives:
        raise ResearchError(f"Unknown objective {objective}")
    fit = minimize(objectives[objective], np.full(n, 1 / n), bounds=[(0, max_weight)] * n, constraints={"type": "eq", "fun": lambda w: w.sum() - 1}, method="SLSQP")
    if not fit.success:
        raise ResearchError(f"Optimiser did not converge: {fit.message}")
    w = np.clip(fit.x, 0, None)
    ret, vol = port(w)
    return {"objective": objective, "weights": {c: float(x) for c, x in zip(prices.columns, w, strict=True)}, "expected_return": ret, "volatility": vol,
            "sharpe": (ret - rf) / vol, "risk_free": rf, "start": r.index[0].strftime("%Y-%m-%d"), "end": r.index[-1].strftime("%Y-%m-%d")}


def factor_regression(asset: pd.Series, factors: pd.DataFrame) -> dict:
    data = pd.concat([asset.rename("asset"), factors], axis=1).dropna()
    if len(data) < 60:
        raise ResearchError("Need 60 overlapping observations.")
    y, x = data["asset"].to_numpy(), np.column_stack([np.ones(len(data)), data[factors.columns].to_numpy()])
    beta, *_ = np.linalg.lstsq(x, y, rcond=None)
    resid = y - x @ beta
    dof = len(y) - x.shape[1]
    se = np.sqrt(np.diag(resid @ resid / dof * np.linalg.inv(x.T @ x)))
    return {"alpha_annual": float(beta[0] * TRADING_DAYS), "alpha_t": float(beta[0] / se[0]), "r_squared": float(1 - resid.var() / y.var()), "n": len(y),
            "betas": {c: {"beta": float(beta[i + 1]), "t": float(beta[i + 1] / se[i + 1])} for i, c in enumerate(factors.columns)}}
