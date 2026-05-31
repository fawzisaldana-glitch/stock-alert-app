// Smart Money PWA — clarity-first: every number labeled, every section explained.
let A = null, BILL = null, MACRO = null, POL = null, VAL = null, VIEW = "home";

const esc = s => String(s == null ? "" : s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const safeUrl = u => /^https?:\/\//i.test(String(u || "")) ? u : "#";
// Validates a relative report path. Locks to reports/<TICKER>.xlsx so a malicious
// ticker string (javascript:, ../, embedded HTML) can't slip into an <a href>.
const safeReportUrl = u => /^reports\/[A-Z0-9.\-]{1,12}_research\.xlsx$/.test(String(u || "")) ? u : "#";
const M = n => { n = Number(n) || 0; return n >= 1e9 ? "$" + (n / 1e9).toFixed(1) + "B" : n >= 1e6 ? "$" + (n / 1e6).toFixed(0) + "M" : "$" + Math.round(n); };
const ago = ts => { const s = Math.max(1, Math.floor(Date.now() / 1000 - (ts || 0))); return s < 3600 ? Math.floor(s / 60) + "m" : s < 86400 ? Math.floor(s / 3600) + "h" : Math.floor(s / 86400) + "d"; };
const tc = s => String(s || "").toLowerCase().replace(/\b\w/g, c => c.toUpperCase());
const $ = id => document.getElementById(id);

const MGR = { "BERKSHIRE": "Warren Buffett · Berkshire", "SCION": "Michael Burry · Scion", "PERSHING": "Bill Ackman · Pershing Sq", "APPALOOSA": "David Tepper · Appaloosa", "DUQUESNE": "Druckenmiller · Duquesne", "THIRD POINT": "Dan Loeb · Third Point" };
const fundName = e => { const u = String(e || "").toUpperCase(); for (const k in MGR) if (u.includes(k)) return MGR[k]; return tc(e); };

const intro = (t, d) => `<div class="intro"><h2>${esc(t)}</h2><p>${d}</p></div>`;
const field = (l, v) => `<div class="f"><div class="lbl">${esc(l)}</div><div class="val">${v}</div></div>`;
const kv = (k, v) => `<div class="kv"><span class="k">${esc(k)}</span><span class="v">${esc(v)}</span></div>`;

async function getJSON(f) { try { return await (await fetch(f + "?_=" + Date.now(), { cache: "no-store" })).json(); } catch (e) { return null; } }

function go(v) {
  document.querySelectorAll(".tab").forEach(t => t.classList.toggle("on", t.dataset.view === v));
  VIEW = v; route(); window.scrollTo(0, 0);
}

function route() {
  if (VIEW === "home") renderHome();
  else if (VIEW === "alerts") renderAlerts();
  else if (VIEW === "billionaires") renderBillionaires();
  else if (VIEW === "macro") renderMacro();
  else if (VIEW === "research") renderResearch();
  else if (VIEW === "politicians") {
    if (POL === null) { $("list").innerHTML = '<div class="empty">Loading…</div>'; getJSON("politicians.json").then(p => { POL = p || { recent: [] }; if (VIEW === "politicians") renderPoliticians(); }); }
    else renderPoliticians();
  }
}

function renderHome() {
  const o = (MACRO && MACRO.overall) || "?";
  const col = o === "GREEN" ? "g" : o === "RED" ? "r" : "a";
  const reds = MACRO ? MACRO.reds : 0;
  const con = (BILL && BILL.consensus) || [];
  const top = (A && A.alerts && A.alerts.slice().sort((a, b) => b.score - a.score)[0]);
  let h = intro("Today at a glance", "Your smart-money signals, ordered by how much edge they actually carry. Tap any card to dig in.");
  h += `<div class="c tap" onclick="go('macro')"><div class="c-h"><span class="name">Market regime</span><span class="pill ${col}">${esc(o)}</span></div>
    <div class="line">${reds} of 5 recession gauges red. ${reds >= 2 ? "<b>Consider trimming risk.</b>" : "No recession warning — <b>stay invested &amp; disciplined.</b>"}</div><div class="hint">Live de-risk dashboard →</div></div>`;
  if (con.length) {
    h += `<div class="c tap" onclick="go('billionaires')"><div class="c-h"><span class="name">Billionaire consensus</span><span class="chip">${con.length} names</span></div>
      <div class="line">Stocks multiple famous funds hold — the strongest read here:</div>` +
      con.slice(0, 4).map(c => kv(tc(c.name), (c.funds || []).length + " funds")).join("") + `<div class="hint">See each fund's buys →</div></div>`;
  }
  if (top) {
    h += `<div class="c tap" onclick="go('alerts')"><div class="c-h"><span class="name">Top catalyst alert</span><span class="pill g">${Math.round(top.score)}</span></div>
      <div class="line"><b>${esc(top.ticker)}</b> — ${esc(top.headline)}</div><div class="hint">All catalyst alerts →</div></div>`;
  }
  h += `<div class="c tap" onclick="go('research')"><div class="c-h"><span class="name">Research library</span><span class="chip">cited</span></div>
    <div class="line">Recession, bond, and bubble research — what's been verified and where it lives.</div></div>`;
  $("list").innerHTML = h;
}

// Valuation block — uses VAL.valuations[ticker] populated by valuation.py.
// Shows DCF intrinsic vs market, peer percentile multiples, blended cheapness. Honest about model confidence.
function valuationBlock(ticker) {
  const v = VAL && VAL.valuations && VAL.valuations[ticker];
  if (!v) return "";
  // Free-tier FMP only unlocks ratios/statements for a sample symbol set; non-sample
  // tickers come back with no factors. Don't render a content-free "Valuation —" block.
  const _m = v.my_metrics || {};
  const _hasMetric = ["pe", "ev_ebitda", "ev_rev"].some(k => _m[k] != null && !isNaN(_m[k]));
  const _hasSignal = v.cheapness != null || (v.intrinsic_value != null && !isNaN(v.intrinsic_value)) || _hasMetric;
  if (!_hasSignal) return "";
  const ch = v.cheapness;
  const chCls = ch == null ? "" : ch >= 0.6 ? "g" : ch >= 0.4 ? "a" : "r";
  const chTxt = ch == null ? "—" : (ch >= 0.6 ? "cheap" : ch >= 0.4 ? "fair" : "rich") + ` (${ch.toFixed(2)})`;
  const mos = v.margin_of_safety;
  const mosTxt = mos == null ? "—" : (mos > 0 ? "+" : "") + (mos * 100).toFixed(0) + "%";
  const mosCls = mos == null ? "" : mos >= 0.2 ? "g" : mos >= -0.1 ? "a" : "r";
  const pp = v.peer_pct || {};
  const m = v.my_metrics || {};
  const pct = (key) => pp[key] == null ? "—" : (pp[key] * 100).toFixed(0) + "th";
  const has = (x) => x != null && !isNaN(x);
  // kv() escapes its value (right for plain text). These two rows inject trusted,
  // numeric-derived HTML (pills), so use a non-escaping variant — chCls/mosCls are from a
  // fixed class set and chTxt/mosTxt are number-formatted, so there's no untrusted input.
  const kvHtml = (k, vHtml) => `<div class="kv"><span class="k">${esc(k)}</span><span class="v">${vHtml}</span></div>`;
  return `<div class="line"><b>Valuation</b> <span class="chip">${esc(v.confidence)} confidence</span></div>` +
    kvHtml("Blended cheapness", `<span class="pill ${chCls}" style="margin:0">${esc(chTxt)}</span>`) +
    (has(v.intrinsic_value) ? kvHtml("DCF intrinsic / market",
      `$${v.intrinsic_value.toFixed(2)} / $${(v.market_price || 0).toFixed(2)} <span class="pill ${mosCls}" style="margin-left:6px">${esc(mosTxt)}</span>`) : "") +
    (has(m.pe) ? kv("P/E (TTM)", `${m.pe.toFixed(1)}× · ${pct("pe")} pct vs peers`) : "") +
    (has(m.ev_ebitda) ? kv("EV / EBITDA", `${m.ev_ebitda.toFixed(1)}× · ${pct("ev_ebitda")} pct vs peers`) : "") +
    (has(m.ev_rev) ? kv("EV / Revenue", `${m.ev_rev.toFixed(1)}× · ${pct("ev_rev")} pct vs peers`) : "") +
    `<div class="hint">Lite DCF — directional, not gospel. Lower percentile = cheaper than peers.</div>`;
}

function renderAlerts() {
  const items = ((A && A.alerts) || []).slice().sort((a, b) => b.score - a.score);
  let h = intro("Catalyst alerts", "Fresh smart-money catalysts, scored 0–100. Insider clusters are the strongest signal; gov contracts are experimental. Tap a card for the full reasoning.");
  if (!items.length) { $("list").innerHTML = h + '<div class="empty">No alerts yet — run the engine to populate.</div>'; return; }
  h += items.map(a => {
    const sc = Math.round(Number(a.score) || 0), cls = sc >= 70 ? "g" : sc >= 45 ? "a" : "";
    const ty = a.type === "insider_cluster" ? "Insider cluster" : a.type === "contract" ? "Gov contract" : "Signal";
    const d = a.details || {};
    const det = a.type === "insider_cluster"
      ? kv("Insiders buying", Number(d.insiders) || 0) + kv("Total bought", M(d.total_value)) + (d.owners ? `<div class="line">${esc(d.owners)}</div>` : "")
      : kv("Award (lifetime)", M(d.amount)) + kv("Agency", d.agency || "—") + kv("Start date", d.action_date || "—");
    const rawReport = VAL && VAL.reports && VAL.reports[a.ticker];
    const reportLink = (rawReport && safeReportUrl(rawReport) !== "#")
      ? `<a href="${esc(safeReportUrl(rawReport))}" target="_blank" rel="noopener">📊 Open full DCF + comps Excel ↗</a>`
      : "";
    return `<div class="c tap" onclick="this.classList.toggle('open')">
      <div class="c-h"><span class="tk">${esc(a.ticker)}</span><span class="chip">${esc(ty)}</span><span class="pill ${cls}">${sc}</span></div>
      <div class="fields">${field("Sector", esc(a.sector || "—"))}${field("Signal strength", sc >= 70 ? "Strong" : sc >= 45 ? "Medium" : "Watch")}</div>
      <div class="det"><div class="line">${esc(a.why)}</div>${det}${valuationBlock(a.ticker)}<div class="hint"><a href="${safeUrl(a.link)}" target="_blank" rel="noopener">Open source filing ↗</a> ${reportLink}</div></div></div>`;
  }).join("");
  $("list").innerHTML = h;
}

function renderBillionaires() {
  if (!BILL) { $("list").innerHTML = '<div class="empty">Loading…</div>'; return; }
  let h = intro("Billionaire holdings", "What famous funds filed last quarter (SEC 13F). Idea-generation, not timing — the data is ~45 days old and longs-only.");
  const con = BILL.consensus || [];
  if (con.length) {
    h += `<div class="c"><div class="c-h"><span class="name">★ Consensus picks</span><span class="chip">held by 2+ funds</span></div>
      <div class="line">The strongest read here — names multiple of these funds own:</div>` +
      con.map(c => kv(tc(c.name), (c.funds || []).join(" · "))).join("") + `</div>`;
  }
  h += (BILL.funds || []).map(f => {
    const nb = f.new_buys || [], top = (f.top || []).slice(0, 5);
    return `<div class="c tap" onclick="this.classList.toggle('open')">
      <div class="c-h"><span class="name">${esc(fundName(f.entity))}</span><span class="pill">${M(f.portfolio)}</span></div>
      <div class="fields">${field("Holdings", Number(f.holdings) || 0)}${field("Filed for", esc(f.report))}${field("New buys", nb.length)}${field("Biggest holding", top[0] ? esc(tc(top[0].issuer)) : "—")}</div>
      <div class="det">${nb.length ? `<div class="lbl">New positions this quarter</div>` + nb.map(b => kv(tc(b.issuer), M(b.value))).join("") : ""}
        <div class="lbl" style="margin-top:11px">Top holdings</div>${top.map(b => kv(tc(b.issuer), M(b.value))).join("")}</div></div>`;
  }).join("");
  $("list").innerHTML = h;
}

function renderMacro() {
  if (!MACRO) { $("list").innerHTML = '<div class="empty">Loading…</div>'; return; }
  const o = MACRO.overall || "?", col = o === "GREEN" ? "g" : o === "RED" ? "r" : "a";
  let h = intro("Recession dashboard", "Five timing gauges from live Fed data. All green = no recession warning. Only go defensive if 2+ turn red — never act on one alone.");
  h += `<div class="c"><div class="c-h"><span class="name">Overall</span><span class="pill ${col}">${esc(o)}</span></div>
    <div class="line">${MACRO.reds} of 5 gauges red · updated ${ago(MACRO.updated)} ago</div>
    <div class="legend"><span><i class="sw" style="background:var(--green)"></i>clear</span><span><i class="sw" style="background:var(--amber)"></i>watch</span><span><i class="sw" style="background:var(--red)"></i>red</span></div></div>`;
  for (const k of Object.keys(MACRO.gauges || {})) {
    const g = MACRO.gauges[k], c = g.red ? "r" : g.warn ? "a" : "g";
    h += `<div class="c"><div class="c-h"><span class="name" style="font-size:15px">${esc(k)}</span><span class="pill ${c}">${esc(String(g.value))}${esc(g.unit || "")}</span></div>
      <div class="line">Turns red when <b>${esc(g.trigger || "")}</b></div></div>`;
  }
  const cp = (MACRO.context || {}).cape || {};
  if (cp.value != null) h += `<div class="c"><div class="c-h"><span class="name" style="font-size:15px">Valuation · Shiller CAPE</span><span class="pill a">${esc(String(cp.value))}x</span></div>
    <div class="line">Stretched (~98th percentile). But valuation predicts <b>low long-run returns</b>, <b>not</b> a crash date — context only, not a timing signal.</div></div>`;
  $("list").innerHTML = h;
}

function renderPoliticians() {
  let h = intro("Politician trades", "Congressional disclosures — informational only, NOT a buy signal. Lagged weeks-to-months and a weak edge (research ranked it last).");
  if (!POL || !POL.recent || !POL.recent.length) {
    $("list").innerHTML = h + '<div class="empty">No data yet.<br>Add a free <b>FMP_API_KEY</b> and run <b>politicians.py</b> to populate.</div>'; return;
  }
  if (POL.leaders && POL.leaders.length) {
    h += `<div class="c"><div class="c-h"><span class="name">Most active</span><span class="chip">approx win-rate</span></div>` +
      POL.leaders.map(l => kv(l.name, `${l.trades} buys · ${l.win_rate}% win · ${l.avg_return > 0 ? "+" : ""}${l.avg_return}%`)).join("") + `</div>`;
  }
  h += (POL.recent || []).map(t => `<div class="c"><div class="c-h"><span class="tk">${esc(t.ticker)}</span><span class="chip">${esc(t.name)}</span><span class="pill ${t.ret > 0 ? "g" : ""}">${t.ret == null ? "—" : (t.ret > 0 ? "+" : "") + t.ret + "%"}</span></div><div class="line">${esc(t.chamber)} · bought ${esc(t.date)}</div></div>`).join("");
  $("list").innerHTML = h;
}

function renderResearch() {
  const items = [
    ["Market Edge Framework", "Your max-edge view: process over prediction, regime-dialing, live de-risk dashboard.", "youtube-research\\market-edge.md"],
    ["Recession research", "Global yields = fiscal/inflation, NOT recession. Every gauge green (~15%).", "market-edge.md §4"],
    ["Bubble research", "Expensive (CAPE ~98th pct) but a return-predictor, NOT a crash timer.", "market-edge.md §4b"],
    ["Insider clusters", "Strongest signal — SEC Form-4 open-market cluster buys.", "Alerts tab"],
    ["Billionaire 13F", "What the greats hold last quarter (45-day lag).", "Billionaires tab"],
    ["YouTube watch + verify", "Distill + fact-check creator videos (Graham, Andrei).", "youtube-research\\yt_fetch.py"]
  ];
  $("list").innerHTML = intro("Research library", "Everything researched and verified — and exactly where it lives.") +
    items.map(([t, d, w]) => `<div class="c"><div class="c-h"><span class="name" style="font-size:16px">${esc(t)}</span></div><div class="line">${esc(d)}</div><div class="hint">📁 ${esc(w)}</div></div>`).join("");
}

async function boot() {
  [A, BILL, MACRO, VAL] = await Promise.all([getJSON("alerts.json"), getJSON("billionaires.json"), getJSON("macro.json"), getJSON("valuation.json")]);
  const o = MACRO && MACRO.overall;
  $("statusmini").innerHTML = o ? `macro <b style="color:${o === "GREEN" ? "var(--green)" : o === "RED" ? "var(--red)" : "var(--amber)"}">${esc(o)}</b>` : "";
  $("sub").textContent = `${(A && A.count) || 0} alerts · ${(BILL && BILL.funds && BILL.funds.length) || 0} funds · updated ${ago((A && A.updated) || (MACRO && MACRO.updated))} ago`;
  route();
}

$("tabs").addEventListener("click", e => { if (e.target.classList.contains("tab")) go(e.target.dataset.view); });
if ("serviceWorker" in navigator) navigator.serviceWorker.register("sw.js").catch(() => {});
boot();
setInterval(() => { if (["home", "alerts", "macro"].includes(VIEW)) boot(); }, 120000);
