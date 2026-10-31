"use client";

import { Flash, Fresh, Panel, Stat, State } from "@/components/ui";
import { ChangePill } from "@/components/widgets";
import { EChart, lineOption } from "@/components/EChart";
import { useEnvelope } from "@/lib/api";
import { compact, num, pct, ratioPct, tone } from "@/lib/format";

type Coin = { id: string; symbol: string; name: string; price: number; market_cap: number; volume_24h: number; chg_24h: number | null; chg_7d: number | null; chg_30d: number | null };
type Networks = { bitcoin: { height: number; hashrate_ehs: number; mempool_tx: number; difficulty: number; fees_sat_vb: { fastestFee: number }; hashrate_history: { time: number; ehs: number }[] } | null; ethereum: { height: number; tx_count: number; gas_price_gwei: number; gas_utilisation: number } | null };
type Defi = { chains: { name: string; tvl: number }[]; stablecoins: { name: string; symbol: string; supply_usd: number; chg_30d: number | null }[]; stablecoin_total: number };

type Live = { symbol: string; name: string; price: number; change_pct: number };

export default function Crypto() {
  const live = useEnvelope<Live[]>("/api/crypto/live", { refreshInterval: 5_000 });
  const m = useEnvelope<Coin[]>("/api/crypto/markets", { refreshInterval: 180_000 });
  const n = useEnvelope<Networks>("/api/crypto/networks", { refreshInterval: 300_000 });
  const d = useEnvelope<Defi>("/api/crypto/defi");
  const btc = n.data?.data.bitcoin;
  const eth = n.data?.data.ethereum;
  return (
    <div className="page">
      <div className="bento">{live.data?.data.map((c) => (
        <section key={c.symbol} className="panel" style={{ "--span": 2 } as React.CSSProperties}><div className="tile-link market-tile" style={{ minHeight: 110 }}>
          <span className="name">{c.name}</span>
          <span><Flash value={c.price}><span className="price">{num(c.price, c.price < 10 ? 4 : 2)}</span></Flash><br /><ChangePill value={c.change_pct} /></span>
        </div></section>))}
      </div>
      <div className="row muted" style={{ fontSize: 12 }}><Fresh meta={live.data?.meta} /> Updates every 5 seconds. {live.data?.meta.note}</div>
      <section className="panel"><div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))" }}>
        <Stat k="BTC block height" v={btc ? btc.height.toLocaleString() : "—"} /><Stat k="BTC hashrate" v={`${num(btc?.hashrate_ehs, 0)} EH/s`} /><Stat k="BTC mempool" v={compact(btc?.mempool_tx)} s="transactions" /><Stat k="BTC fee" v={`${btc?.fees_sat_vb.fastestFee ?? "—"} sat/vB`} />
        <Stat k="ETH block" v={eth ? eth.height.toLocaleString() : "—"} /><Stat k="ETH gas" v={`${num(eth?.gas_price_gwei, 3)} gwei`} /><Stat k="ETH block use" v={ratioPct(eth?.gas_utilisation, 0)} s={eth ? `${eth.tx_count} tx in last block` : undefined} /><Stat k="Stablecoin supply" v={compact(d.data?.data.stablecoin_total, "$")} />
      </div></section>
      <div className="grid-2">
        <Panel title="Market" meta={m.data?.meta} style={{ height: 460 }}>
          <State loading={m.isLoading} error={m.error}>
            <table className="t mono"><thead><tr><th>Asset</th><th>Price</th><th>24h</th><th>7d</th><th>30d</th><th>Mkt cap</th><th>Volume</th></tr></thead>
              <tbody>{m.data?.data.map((c) => <tr key={c.id}><td>{c.symbol} <span className="muted">{c.name}</span></td><td>{num(c.price, c.price < 1 ? 4 : 2)}</td><td className={tone(c.chg_24h)}>{pct(c.chg_24h)}</td><td className={tone(c.chg_7d)}>{pct(c.chg_7d)}</td><td className={tone(c.chg_30d)}>{pct(c.chg_30d)}</td><td>{compact(c.market_cap, "$")}</td><td>{compact(c.volume_24h, "$")}</td></tr>)}</tbody></table>
          </State>
        </Panel>
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          <Panel title="Bitcoin hashrate, 3 months" meta={n.data?.meta}><EChart height={190} option={lineOption([{ name: "EH/s", points: btc?.hashrate_history.map((p) => [new Date(p.time * 1000).toISOString().slice(0, 10), +p.ehs.toFixed(0)]) ?? [] }])} /></Panel>
          <Panel title="DeFi and stablecoins" meta={d.data?.meta} style={{ flex: 1 }}>
            <State loading={d.isLoading} error={d.error}><div className="grid-2">
              <table className="t mono"><thead><tr><th>Chain</th><th>TVL</th></tr></thead><tbody>{d.data?.data.chains.slice(0, 7).map((c) => <tr key={c.name}><td>{c.name}</td><td>{compact(c.tvl, "$")}</td></tr>)}</tbody></table>
              <table className="t mono"><thead><tr><th>Stablecoin</th><th>Supply</th><th>30d</th></tr></thead><tbody>{d.data?.data.stablecoins.slice(0, 7).map((s) => <tr key={s.symbol}><td>{s.symbol}</td><td>{compact(s.supply_usd, "$")}</td><td className={tone(s.chg_30d)}>{ratioPct(s.chg_30d, 1, true)}</td></tr>)}</tbody></table>
            </div></State>
          </Panel>
        </div>
      </div>
    </div>
  );
}
