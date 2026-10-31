"""Discounted cash flow. Every output is an estimate derived from the stated assumptions."""

from dataclasses import dataclass


class ValuationError(ValueError):
    pass


@dataclass
class DcfInput:
    base_fcf: float
    growth: float
    terminal_growth: float
    discount_rate: float
    years: int = 10
    fade: bool = True
    net_debt: float = 0.0
    shares: float = 1.0

    def validate(self) -> None:
        if self.discount_rate <= self.terminal_growth:
            raise ValuationError("Discount rate must exceed terminal growth, or terminal value is undefined.")
        if not 1 <= self.years <= 30:
            raise ValuationError("Projection length must be between 1 and 30 years.")
        if self.shares <= 0:
            raise ValuationError("Share count must be positive.")
        if self.base_fcf <= 0:
            raise ValuationError("Base free cash flow is not positive, so a perpetuity DCF is not meaningful.")


def dcf(p: DcfInput) -> dict:
    p.validate()
    rows, fcf, pv_sum = [], p.base_fcf, 0.0
    for year in range(1, p.years + 1):
        g = p.growth + (p.terminal_growth - p.growth) * (year - 1) / max(p.years - 1, 1) if p.fade else p.growth
        fcf *= 1 + g
        pv = fcf / (1 + p.discount_rate) ** year
        pv_sum += pv
        rows.append({"year": year, "growth": g, "fcf": fcf, "pv": pv})
    terminal = fcf * (1 + p.terminal_growth) / (p.discount_rate - p.terminal_growth)
    pv_terminal = terminal / (1 + p.discount_rate) ** p.years
    ev = pv_sum + pv_terminal
    equity = ev - p.net_debt
    return {"projection": rows, "pv_fcf": pv_sum, "terminal_value": terminal, "pv_terminal": pv_terminal,
            "enterprise_value": ev, "equity_value": equity, "per_share": equity / p.shares,
            "terminal_share_of_ev": pv_terminal / ev}


def scenarios(p: DcfInput) -> list[dict]:
    out = []
    for label, dg, dr in (("Bear", -0.04, 0.01), ("Base", 0.0, 0.0), ("Bull", 0.04, -0.01)):
        case = DcfInput(**{**p.__dict__, "growth": p.growth + dg, "discount_rate": p.discount_rate + dr})
        out.append({"label": label, "growth": case.growth, "discount_rate": case.discount_rate, "per_share": dcf(case)["per_share"]})
    return out


def sensitivity(p: DcfInput) -> dict:
    rates = [round(p.discount_rate + d, 4) for d in (-0.02, -0.01, 0, 0.01, 0.02)]
    growths = [round(p.terminal_growth + d, 4) for d in (-0.01, -0.005, 0, 0.005, 0.01)]
    grid = []
    for r in rates:
        row = []
        for g in growths:
            row.append(None if r <= g else dcf(DcfInput(**{**p.__dict__, "discount_rate": r, "terminal_growth": g}))["per_share"])
        grid.append(row)
    return {"discount_rates": rates, "terminal_growths": growths, "per_share": grid}
