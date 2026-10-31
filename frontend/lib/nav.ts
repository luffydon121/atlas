export type NavItem = { href: string; label: string; key: string; group: string; tagline: string; desc: string; preload?: string[] };

export const NAV: NavItem[] = [
  { href: "/", label: "Today", key: "d", group: "Today", tagline: "", desc: "Your daily briefing" },
  { href: "/markets", label: "Overview", key: "m", group: "Markets", tagline: "Markets. At a glance.", desc: "Sectors, breadth and screener", preload: ["/api/market/overview", "/api/market/screener"] },
  { href: "/chart", label: "Charts", key: "c", group: "Markets", tagline: "Every move. In detail.", desc: "Line, candles and indicators" },
  { href: "/company", label: "Companies", key: "r", group: "Markets", tagline: "Know the business.", desc: "Filings, ratios and valuation" },
  { href: "/crypto", label: "Crypto", key: "b", group: "Markets", tagline: "Crypto. Live.", desc: "Prices, networks and DeFi", preload: ["/api/crypto/live", "/api/crypto/markets"] },
  { href: "/workspace", label: "Workspace", key: "u", group: "Markets", tagline: "", desc: "Resizable pro layout" },
  { href: "/economy", label: "Indicators", key: "e", group: "Economy", tagline: "The economy. Measured.", desc: "US, Australia and euro area", preload: ["/api/econ/dashboard?region=US", "/api/econ/yield-curve"] },
  { href: "/calendar", label: "Calendar", key: "l", group: "Economy", tagline: "What's coming.", desc: "Rate decisions and earnings", preload: ["/api/calendar"] },
  { href: "/map", label: "World map", key: "w", group: "World", tagline: "", desc: "Fourteen live layers" },
  { href: "/satellite", label: "Satellite", key: "s", group: "World", tagline: "See change from orbit.", desc: "Sentinel-2 change detection" },
  { href: "/weather", label: "Weather risk", key: "f", group: "World", tagline: "Weather meets commodities.", desc: "Crop regions against the norm" },
  { href: "/transport", label: "Shipping and air", key: "t", group: "World", tagline: "The world in motion.", desc: "Chokepoints and airports", preload: ["/api/shipping/chokepoints"] },
  { href: "/geopolitics", label: "Geopolitics", key: "g", group: "World", tagline: "Facts first.", desc: "Official and unverified, kept apart" },
  { href: "/alternative", label: "Alternative data", key: "y", group: "World", tagline: "Signals, with the receipts.", desc: "Methods and validation" },
  { href: "/quant", label: "Quant lab", key: "q", group: "Research", tagline: "Test the idea first.", desc: "Backtests and Monte Carlo" },
  { href: "/portfolio", label: "Portfolio", key: "p", group: "Research", tagline: "Everything you own.", desc: "Holdings, risk and paper trading", preload: ["/api/portfolios"] },
  { href: "/alerts", label: "Alerts", key: "a", group: "Research", tagline: "Know when it matters.", desc: "Rules and notifications" },
  { href: "/sources", label: "Sources", key: "o", group: "System", tagline: "Where every number comes from.", desc: "Licences, health and freshness" },
  { href: "/settings", label: "Settings", key: "x", group: "System", tagline: "Make it yours.", desc: "Keys, documents and appearance" },
];

export const GROUPS = ["Markets", "Economy", "World", "Research"] as const;
