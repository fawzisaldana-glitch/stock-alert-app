// Smart Money PWA — clarity-first: every number labeled, every section explained in plain English.
let A = null, BILL = null, MACRO = null, POL = null, VAL = null, VIEW = "home", POL_SORT = "active";

const esc = s => String(s == null ? "" : s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const safeUrl = u => /^https?:\/\//i.test(String(u || "")) ? u : "#";
// Locks report links to reports/<TICKER>_research.xlsx so no javascript:/../ can slip into an href.
const safeReportUrl = u => /^reports\/[A-Z0-9.\-]{1,12}_research\.xlsx$/.test(String(u || "")) ? u : "#";
const M = n => { n = Number(n) || 0; return n >= 1e9 ? "$" + (n / 1e9).toFixed(1) + "B" : n >= 1e6 ? "$" + (n / 1e6).toFixed(0) + "M" : "$" + Math.round(n); };
const ago = ts => { const s = Math.max(1, Math.floor(Date.now() / 1000 - (ts || 0))); return s < 3600 ? Math.floor(s / 60) + "m" : s < 86400 ? Math.floor(s / 3600) + "h" : Math.floor(s / 86400) + "d"; };
const tc = s => String(s || "").toLowerCase().replace(/\b\w/g, c => c.toUpperCase());
const $ = id => document.getElementById(id);

const MGR = { "BERKSHIRE": "Warren Buffett · Berkshire", "SCION": "Michael Burry · Scion", "PERSHING": "Bill Ackman · Pershing Sq", "APPALOOSA": "David Tepper · Appaloosa", "DUQUESNE": "Druckenmiller · Duquesne", "THIRD POINT": "Dan Loeb · Third Point", "BRIDGEWATER": "Ray Dalio · Bridgewater", "ICAHN": "Carl Icahn", "BAUPOST": "Seth Klarman · Baupost", "OAKTREE": "Howard Marks · Oaktree", "SOROS": "George Soros", "RENAISSANCE": "Jim Simons · Renaissance", "TIGER GLOBAL": "Chase Coleman · Tiger Global", "GREENLIGHT": "David Einhorn · Greenlight", "FAIRHOLME": "Bruce Berkowitz", "GOTHAM": "Joel Greenblatt · Gotham", "HIMALAYA": "Li Lu · Himalaya", "MARKEL": "Tom Gayner · Markel", "POLEN": "Polen Capital", "TWEEDY": "Tweedy Browne", "ELLIOTT": "Paul Singer · Elliott", "LONE PINE": "Steve Mandel · Lone Pine", "VIKING": "Andreas Halvorsen · Viking", "COATUE": "Philippe Laffont · Coatue", "ABRAMS": "David Abrams", "HOUNDSTOOTH": "Houndstooth", "AKRE": "Chuck Akre" };
const fundName = e => { const u = String(e || "").toUpperCase(); for (const k in MGR) if (u.includes(k)) return MGR[k]; return tc(e); };

const intro = (t, d) => `<div class="intro"><h2>${esc(t)}</h2><p>${d}</p></div>`;
const field = (l, v) => `<div class="f"><div class="lbl">${esc(l)}</div><div class="val">${v}</div></div>`;
const kv = (k, v) => `<div class="kv"><span class="k">${esc(k)}</span><span class="v">${esc(v)}</span></div>`;
const kvHtml = (k, vHtml) => `<div class="kv"><span class="k">${esc(k)}</span><span class="v">${vHtml}</span></div>`;
// Collapsible "How to read this" explainer (native <details> — no JS, stays clean when closed).
// bodyHtml is author-trusted copy (may contain markup); never interpolate user/feed data unescaped.
const explain = (title, bodyHtml) => `<details class="explain"><summary><span class="i">i</span>${esc(title)}</summary><div class="ebody">${bodyHtml}</div></details>`;
const terms = pairs => `<dl class="gloss">` + pairs.map(([t, d]) => `<dt>${esc(t)}</dt><dd>${d}</dd>`).join("") + `</dl>`;
const sec = (title, tag, tagCls) => `<div class="sec"><span>${esc(title)}</span>${tag ? `<span class="stag ${tagCls || ""}">${esc(tag)}</span>` : ""}</div>`;
// 0–100 signal score → band word + color class. One definition used everywhere.
const band = sc => sc >= 70 ? ["Strong", "g"] : sc >= 45 ? ["Medium", "a"] : ["Watch", ""];

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
  let h = intro("Today at a glance", "Signals that famous investors, insiders, and Congress are acting on — ordered by how much edge each actually carries. Tap any card to dig in.");
  h += explain("New here? Start with this", `This app watches four kinds of "smart money" and explains what each one means:
    <dl class="gloss">
    <dt>Catalyst alerts</dt><dd>Company insiders buying their own stock, + big government contracts. The strongest edge here.</dd>
    <dt>Billionaires</dt><dd>What famous investors bought last quarter (from required SEC filings).</dd>
    <dt>Politicians</dt><dd>Stock trades members of Congress disclosed. Interesting, but a weak/late signal.</dd>
    <dt>Macro</dt><dd>Five recession warning lights from official data — for "risk on / risk off," not stock picking.</dd>
    </dl>Nothing here is advice. It's a starting point for your own research.`);
  h += `<div class="c tap" onclick="go('macro')"><div class="c-h"><span class="name">Market regime</span><span class="pill ${col}">${esc(o)}</span></div>
    <div class="line">${reds} of 5 recession warning lights are red. ${reds >= 2 ? "<b>Consider trimming risk.</b>" : "No recession warning — <b>stay invested &amp; disciplined.</b>"}</div><div class="hint">Tap for all five gauges, explained →</div></div>`;
  if (con.length) {
    h += `<div class="c tap" onclick="go('billionaires')"><div class="c-h"><span class="name">Billionaire consensus</span><span class="chip">${con.length} names</span></div>
      <div class="line">Stocks several famous funds <b>all</b> hold — usually the strongest read on this tab:</div>` +
      con.slice(0, 4).map(c => kv(tc(c.name), (c.funds || []).length + " funds own it")).join("") + `<div class="hint">See each fund's buys →</div></div>`;
  }
  if (top) {
    const [bw, bc] = band(Math.round(top.score));
    h += `<div class="c tap" onclick="go('alerts')"><div class="c-h"><span class="name">Top catalyst alert</span><span class="pill ${bc}">${Math.round(top.score)}/100</span></div>
      <div class="line"><b>${esc(top.ticker)}</b> — ${esc(top.headline)}</div><div class="hint">${esc(bw)} signal · all catalyst alerts →</div></div>`;
  }
  $("list").innerHTML = h;
}

// Valuation block — uses VAL.valuations[ticker]. Shows DCF intrinsic vs market, peer multiples, blended cheapness.
function valuationBlock(ticker) {
  const v = VAL && VAL.valuations && VAL.valuations[ticker];
  if (!v) return "";
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
  const pp = v.peer_pct || {}, m = v.my_metrics || {};
  const pct = (key) => pp[key] == null ? "—" : (pp[key] * 100).toFixed(0) + "th";
  const has = (x) => x != null && !isNaN(x);
  return `<div class="line" style="margin-top:13px"><b>Is it cheap?</b> <span class="chip">${esc(v.confidence)} confidence</span></div>` +
    kvHtml("Cheapness (0 rich → 1 cheap)", `<span class="pill ${chCls}" style="margin:0">${esc(chTxt)}</span>`) +
    (has(v.intrinsic_value) ? kvHtml("Est. fair value / price now",
      `$${v.intrinsic_value.toFixed(2)} / $${(v.market_price || 0).toFixed(2)} <span class="pill ${mosCls}" style="margin-left:6px">${esc(mosTxt)}</span>`) : "") +
    (has(m.pe) ? kv("P/E (price ÷ earnings)", `${m.pe.toFixed(1)}× · ${pct("pe")} pctile vs peers`) : "") +
    (has(m.ev_ebitda) ? kv("EV / EBITDA", `${m.ev_ebitda.toFixed(1)}× · ${pct("ev_ebitda")} pctile vs peers`) : "") +
    (has(m.ev_rev) ? kv("EV / Revenue", `${m.ev_rev.toFixed(1)}× · ${pct("ev_rev")} pctile vs peers`) : "") +
    `<div class="hint">Rough fair-value estimate — directional, not gospel. Lower percentile = cheaper than its peers.</div>`;
}

function renderAlerts() {
  const items = ((A && A.alerts) || []).slice().sort((a, b) => b.score - a.score);
  let h = intro("Catalyst alerts", "Fresh events that often come before a stock moves — scored 0–100 by how strong the signal is.");
  h += explain("How to read this tab", `
    <b>The 0–100 score = how strong the signal is</b> (not a price target, not "how much it'll go up").
    <dl class="gloss">
    <dt>70–100 · Strong</dt><dd>Multiple insiders buying, or a CEO/CFO buying, often plus a cheap valuation.</dd>
    <dt>45–69 · Medium</dt><dd>A real signal, but smaller or with fewer confirmations.</dd>
    <dt>Under 45 · Watch</dt><dd>Weak — keep an eye on it, don't chase it.</dd>
    </dl>
    So <b>LMT at 85</b> just means "a strong signal," not "85% gain." The two kinds of alerts:
    <dl class="gloss">
    <dt>🔓 Insider cluster</dt><dd><b>Strongest edge.</b> Several company insiders bought their <b>own</b> stock with personal cash in a short window. People sell for many reasons but buy for one — they think it's going up.</dd>
    <dt>🏛️ Government contract</dt><dd><b>Experimental.</b> A company won a big federal award. Can lift revenue, but the data lists lifetime award totals (not always fresh news), so verify before acting.</dd>
    </dl>
    Tap any card for the full reasoning and a valuation check.`);
  if (!items.length) { $("list").innerHTML = h + '<div class="empty">No alerts yet — run the engine to populate.</div>'; return; }

  const card = a => {
    const sc = Math.round(Number(a.score) || 0), [bw, bc] = band(sc);
    const d = a.details || {};
    const det = a.type === "insider_cluster"
      ? kv("Insiders buying", Number(d.insiders) || 0) + kv("Total they bought", M(d.total_value)) + (d.owners ? `<div class="line">${esc(d.owners)}</div>` : "")
      : kv("Award (lifetime total)", M(d.amount)) + kv("Agency", d.agency || "—") + kv("Start date", d.action_date || "—");
    const rawReport = VAL && VAL.reports && VAL.reports[a.ticker];
    const reportLink = (rawReport && safeReportUrl(rawReport) !== "#")
      ? `<a href="${esc(safeReportUrl(rawReport))}" target="_blank" rel="noopener">📊 Full DCF + comps (Excel) ↗</a>` : "";
    return `<div class="c tap" onclick="this.classList.toggle('open')">
      <div class="c-h"><span class="tk">${esc(a.ticker)}</span><span class="pill ${bc}">${sc}/100</span></div>
      <div class="fields">${field("Sector", esc(a.sector || "—"))}${field("Signal", bw)}</div>
      <div class="det"><div class="line"><b>Why this matters:</b> ${esc(a.why)}</div>${det}${valuationBlock(a.ticker)}
        <div class="hint"><a href="${safeUrl(a.link)}" target="_blank" rel="noopener">Open source filing ↗</a> ${reportLink}</div></div></div>`;
  };

  const insiders = items.filter(a => a.type === "insider_cluster");
  const contracts = items.filter(a => a.type === "contract");
  const other = items.filter(a => a.type !== "insider_cluster" && a.type !== "contract");
  if (insiders.length) h += sec("Insider clusters", "strongest signal", "strong") +
    `<div class="subnote">Company insiders buying their own stock with personal cash.</div>` + insiders.map(card).join("");
  if (contracts.length) h += sec("Government contracts", "experimental", "exp") +
    `<div class="subnote">Big federal awards — verify the award is fresh news before acting.</div>` + contracts.map(card).join("");
  if (other.length) h += sec("Other signals") + other.map(card).join("");
  $("list").innerHTML = h;
}

function renderBillionaires() {
  if (!BILL) { $("list").innerHTML = '<div class="empty">Loading…</div>'; return; }
  let h = intro("Billionaire holdings", "What famous investors owned at the end of last quarter, from filings they're legally required to make.");
  h += explain("How to read this tab", `
    Big investment funds must file a <b>13F</b> with the SEC every quarter listing their US stock holdings. That's where this comes from.
    <dl class="gloss">
    <dt>★ Consensus picks</dt><dd>Stocks that <b>several</b> of these funds own. When many great investors independently hold the same name, that's the strongest read here.</dd>
    <dt>New positions</dt><dd>Stocks a fund bought for the <b>first</b> time last quarter — fresh conviction.</dd>
    <dt>Why the lag?</dt><dd>13Fs are filed ~45 days <b>after</b> the quarter ends, and only show what they bought, not why. So it's idea-generation — <b>not</b> a "buy now" trigger.</dd>
    </dl>
    Tap any fund to see its new buys and biggest holdings.`);
  const con = BILL.consensus || [];
  if (con.length) {
    h += sec("★ Consensus picks", "held by 2+ funds");
    h += `<div class="c"><div class="line">Names multiple of these funds own — start here:</div>` +
      con.map(c => kv(tc(c.name), (c.funds || []).join(" · "))).join("") + `</div>`;
  }
  const funds = (BILL.funds || []).slice().sort((a, b) => (b.portfolio || 0) - (a.portfolio || 0));
  h += sec(`Funds`, `${funds.length} tracked`);
  h += funds.map(f => {
    const nb = f.new_buys || [], top = (f.top || []).slice(0, 5);
    return `<div class="c tap" onclick="this.classList.toggle('open')">
      <div class="c-h"><span class="name">${esc(fundName(f.entity))}</span><span class="pill">${M(f.portfolio)}</span></div>
      <div class="fields">${field("Holdings", Number(f.holdings) || 0)}${field("Filed for", esc(f.report))}${field("New buys", nb.length)}${field("Biggest holding", top[0] ? esc(tc(top[0].issuer)) : "—")}</div>
      <div class="det">${nb.length ? `<div class="lbl">New positions this quarter</div>` + nb.map(b => kv(tc(b.issuer), M(b.value))).join("") : ""}
        <div class="lbl" style="margin-top:11px">Top holdings</div>${top.map(b => kv(tc(b.issuer), M(b.value))).join("")}</div></div>`;
  }).join("");
  $("list").innerHTML = h;
}

// Plain-English explanation for each macro gauge, keyed by name. Shown when a gauge is tapped.
const GAUGE_HELP = {
  "2s10s (curve)": "The gap between 10-year and 2-year US government bond yields, in percentage points (pp). Normally positive. When it goes <b>negative</b> ('inverts'), a recession has often followed 6–18 months later.",
  "3m10y (curve)": "Like 2s10s but using 3-month vs 10-year yields — the Fed's preferred recession curve. <b>Negative = warning.</b>",
  "NY Fed recession prob": "The New York Fed's model estimate of a US recession within 12 months. Red above 30%.",
  "HY credit spread": "The extra interest investors demand to lend to risky ('high-yield' / junk) companies vs. the government. It <b>spikes when markets fear defaults.</b> Red above 6%.",
  "Sahm rule (jobs)": "An unemployment-based recession alarm: it triggers when the 3-month average jobless rate rises 0.5 above its recent low. A real-time recession detector."
};

function renderMacro() {
  if (!MACRO) { $("list").innerHTML = '<div class="empty">Loading…</div>'; return; }
  const o = MACRO.overall || "?", col = o === "GREEN" ? "g" : o === "RED" ? "r" : "a";
  let h = intro("Recession watch", "Five warning lights built from official US data. This is about “risk-on vs risk-off,” not picking stocks.");
  h += explain("How to read this tab", `
    Each gauge is a recession warning light. Together they answer one question: <b>is now a riskier-than-usual time to be aggressive?</b>
    <dl class="gloss">
    <dt><span class="dotc g"></span>GREEN</dt><dd>Clear — no warning from that gauge.</dd>
    <dt><span class="dotc a"></span>AMBER</dt><dd>Watch — getting closer to its trigger.</dd>
    <dt><span class="dotc r"></span>RED</dt><dd>Triggered — historically a recession warning.</dd>
    <dt>pp</dt><dd>"percentage points" — e.g. 0.76pp is the size of a gap between two interest rates.</dd>
    <dt>The golden rule</dt><dd>Never act on one red gauge. Only consider getting defensive when <b>2 or more</b> turn red together.</dd>
    </dl>
    Tap any gauge below for what it actually measures.`);

  h += `<div class="c"><div class="c-h"><span class="name">Overall</span><span class="pill ${col}">${esc(o)}</span></div>
    <div class="line"><b>${MACRO.reds} of 5</b> warning lights are red · updated ${ago(MACRO.updated)} ago. ${MACRO.reds >= 2 ? "Two or more red — <b>consider trimming risk.</b>" : "Below the 2-red threshold — <b>no recession warning.</b>"}</div></div>`;

  h += sec("The five gauges", "tap to learn each");
  for (const k of Object.keys(MACRO.gauges || {})) {
    const g = MACRO.gauges[k], c = g.red ? "r" : g.warn ? "a" : "g", cw = g.red ? "RED" : g.warn ? "AMBER" : "GREEN";
    h += `<div class="c tap" onclick="this.classList.toggle('open')"><div class="c-h"><span class="name" style="font-size:15px">${esc(k)}</span><span class="pill ${c}">${esc(String(g.value))}${esc(g.unit || "")}</span></div>
      <div class="line">Status: <b>${cw}</b> · turns red when <b>${esc(g.trigger || "")}</b></div>
      <div class="det"><div class="line">${GAUGE_HELP[k] || ""}</div></div></div>`;
  }
  const cp = (MACRO.context || {}).cape || {};
  if (cp.value != null) h += sec("Bonus · how expensive is the market?") +
    `<div class="c tap" onclick="this.classList.toggle('open')"><div class="c-h"><span class="name" style="font-size:15px">Shiller CAPE</span><span class="pill a">${esc(String(cp.value))}×</span></div>
    <div class="line">Historically expensive (~98th percentile).</div>
    <div class="det"><div class="line"><b>CAPE</b> = price ÷ the last 10 years of inflation-adjusted earnings — a long-term "expensiveness" gauge. Important: a high CAPE predicts <b>lower returns over the next decade</b>, it does <b>NOT</b> predict a crash or when one happens. Context only.</div></div></div>`;
  $("list").innerHTML = h;
}

function setPolSort(s) { POL_SORT = s; renderPoliticians(); }

function renderPoliticians() {
  let h = intro("Politician trades", "Stock trades that members of Congress disclosed. Interesting to watch — but a weak, late signal, not a buy trigger.");
  h += explain("How to read this tab — and the HD / “house” confusion", `
    Members of Congress must disclose their stock trades. <b>Tap a person to see only their trades.</b>
    <dl class="gloss">
    <dt>"House" / "Senate"</dt><dd>Which chamber of Congress the person serves in — <b>not</b> a property. "Rep." = House, "Sen." = Senate.</dd>
    <dt>The ticker (e.g. HD)</dt><dd>The <b>stock</b> they traded. HD = Home Depot, PH = Parker-Hannifin. A company symbol — <b>nothing to do with buying a house.</b></dd>
    <dt>"avg" / "% since"</dt><dd>Roughly how their buys have done since the disclosed date — approximate, and disclosure lags the real trade by weeks.</dd>
    <dt>Sort buttons</dt><dd><b>Active</b> = most trades · <b>Recent</b> = newest first · <b>Profitable</b> = best average return on buys.</dd>
    </dl>
    Heads-up: research ranks congressional trading among the <b>weakest</b> signals (lagged, small samples) — fun to know, not an edge. This shows recent disclosures from a free feed (~20-30 members), not the full roster.`);
  const pols = (POL && POL.politicians) || [];
  if (!pols.length) {
    $("list").innerHTML = h + '<div class="empty">No data yet.<br>Run <b>politicians.py</b> to populate.</div>'; return;
  }

  // sort toggle (segmented control)
  const seg = (id, label) => `<span class="segbtn ${POL_SORT === id ? "on" : ""}" onclick="setPolSort('${id}')">${label}</span>`;
  h += `<div class="seg">${seg("active", "Most active")}${seg("recent", "Most recent")}${seg("profitable", "Most profitable")}</div>`;

  const sorted = pols.slice();
  if (POL_SORT === "recent") sorted.sort((a, b) => String(b.last_date).localeCompare(String(a.last_date)));
  else if (POL_SORT === "profitable") sorted.sort((a, b) => (b.avg_return == null ? -1e9 : b.avg_return) - (a.avg_return == null ? -1e9 : a.avg_return));
  else sorted.sort((a, b) => b.trades - a.trades);

  h += sorted.map(p => {
    const pre = /sen/i.test(p.chamber) ? "Sen." : "Rep.";
    const ar = p.avg_return == null ? null : (p.avg_return > 0 ? "+" : "") + p.avg_return + "%";
    const arCls = p.avg_return == null ? "" : p.avg_return > 0 ? "g" : "r";
    const pill = ar ? `<span class="pill ${arCls}">${esc(ar)} avg</span>` : `<span class="pill">${p.trades} trades</span>`;
    const items = (p.items || []).map(t => {
      const verb = (t.type || "").toLowerCase().startsWith("purchase") || (t.type || "").toLowerCase().startsWith("buy") ? "bought" : "sold";
      const retTxt = t.ret == null ? "" : ` <span class="pill ${t.ret > 0 ? "g" : "r"}" style="margin-left:6px">${t.ret > 0 ? "+" : ""}${t.ret}%</span>`;
      const co = t.company ? tc(t.company) : "";
      return `<div class="kv"><span class="k">${esc(t.ticker || "—")}${co ? " · " + esc(co) : ""}</span><span class="v">${esc(verb)} ${esc(t.date)}${retTxt}</span></div>`;
    }).join("");
    return `<div class="c tap" onclick="this.classList.toggle('open')">
      <div class="c-h"><span class="name" style="font-size:16px">${esc(pre + " " + p.name)}</span>${pill}</div>
      <div class="fields">${field("Chamber", esc(p.chamber))}${field("Disclosed trades", p.trades)}${field("Buys", p.buys)}${field("Last trade", esc(p.last_date || "—"))}</div>
      <div class="det"><div class="lbl">Their disclosed trades</div>${items}
        ${p.win_rate != null ? `<div class="hint">~${p.win_rate}% of their buys are positive since the disclosed date (approximate).</div>` : ""}</div></div>`;
  }).join("");
  $("list").innerHTML = h;
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
