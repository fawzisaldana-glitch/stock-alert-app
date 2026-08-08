// Bronco Painting CRM — GoHighLevel-parity section, Smart Money OS skin.
// Layout & information architecture mirror GHL's sub-account app; all code, icons and data are original.
let D = null;                      // bronco.json
let RANGE = 90;                    // dashboard date window (days)
let OPP_FILTER = "open";           // kanban: open | won | lost | all
let CONV_ID = null, CONV_FILTER = "all", CONTACT_Q = "", CONTACT_TYPE = "all";
const NOW = Date.now();
// theme: default = Smart Money charcoal/gold; "ghl" = HighLevel light (persisted per device)
if (localStorage.getItem("bronco-theme") === "ghl") document.body.classList.add("ghl");

const esc = s => String(s == null ? "" : s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const $ = id => document.getElementById(id);
const money = n => "$" + Math.round(Number(n) || 0).toLocaleString("en-US");
const moneyK = n => { n = Number(n) || 0; return n >= 1000 ? "$" + (n / 1000).toFixed(n >= 10000 ? 0 : 1) + "k" : "$" + Math.round(n); };
const initials = n => String(n || "?").split(/\s+/).map(w => w[0]).slice(0, 2).join("").toUpperCase();
const pct = (a, b) => b ? Math.round(a / b * 100) : 0;

// ---- day-offset helpers (data stores offsets so the demo stays evergreen) ----
const dAgo = (days, hours) => new Date(NOW - (days || 0) * 864e5 - (hours || 0) * 36e5);
const dIn = days => new Date(NOW + (days || 0) * 864e5);
const WD = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const MO = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const fmtAgo = (days, hours) => {
  if ((days || 0) === 0) { const h = hours == null ? 0 : hours; return h <= 0 ? "Just now" : h + "h ago"; }
  if (days === 1) return "Yesterday";
  if (days < 7) return WD[dAgo(days).getDay()];
  const d = dAgo(days); return MO[d.getMonth()] + " " + d.getDate();
};
const fmtIn = days => {
  if (days === 0) return "Today";
  if (days === 1) return "Tomorrow";
  const d = dIn(days); return WD[d.getDay()] + ", " + MO[d.getMonth()] + " " + d.getDate();
};
const fmtDue = days => days < 0 ? Math.abs(days) + "d overdue" : days === 0 ? "Due today" : days === 1 ? "Due tomorrow" : "Due in " + days + "d";
const time12 = t => { const [h, m] = String(t || "9:00").split(":").map(Number); const ap = h >= 12 ? "pm" : "am"; return ((h % 12) || 12) + ":" + String(m).padStart(2, "0") + " " + ap; };

// ---- icons (original inline SVGs, GHL-style stroke icons) ----
const I = {
  launchpad: '<path d="M12 15c-2-6 1-11 5.5-12.5C18 7 16 12 12 15zM12 15l-3.5-3.5M9.5 13.5c-2 .5-3.5 2-4 5 3-.5 4.5-2 5-4M14 10a1.4 1.4 0 1 0 0-2.8 1.4 1.4 0 0 0 0 2.8z"/>',
  dash: '<rect x="3.5" y="3.5" width="7" height="7" rx="1.6"/><rect x="13.5" y="3.5" width="7" height="7" rx="1.6"/><rect x="3.5" y="13.5" width="7" height="7" rx="1.6"/><rect x="13.5" y="13.5" width="7" height="7" rx="1.6"/>',
  convo: '<path d="M21 12a8 8 0 0 1-8 8H4l1.5-3A8 8 0 1 1 21 12z"/><path d="M8.5 10.5h7M8.5 13.5h4.5"/>',
  cal: '<rect x="3.5" y="5" width="17" height="15.5" rx="2"/><path d="M3.5 9.8h17M8 2.8V6.5M16 2.8V6.5"/>',
  contacts: '<circle cx="9" cy="8.2" r="3.2"/><path d="M3.5 19.5c.6-3.2 2.8-5 5.5-5s4.9 1.8 5.5 5M15.5 5.4a3.2 3.2 0 0 1 0 5.7M17.5 14.8c1.7.6 2.7 2 3 4.2"/>',
  opps: '<path d="M4 4h16l-5.5 7v6L10 20v-9L4 4z"/>',
  pay: '<rect x="3" y="5.5" width="18" height="13" rx="2"/><path d="M3 10h18M7 15h4"/>',
  mktg: '<path d="M4 13.5v-3l11-5v13l-11-5zM15 8.5c2 .5 3 1.7 3 3s-1 2.5-3 3M6.5 14.5 8 20h2.5l-1.2-5"/>',
  auto: '<circle cx="6" cy="6" r="2.5"/><circle cx="18" cy="6" r="2.5"/><circle cx="12" cy="18" r="2.5"/><path d="M6 8.5v2a3 3 0 0 0 3 3h6a3 3 0 0 0 3-3v-2M12 13.5v2"/>',
  sites: '<circle cx="12" cy="12" r="8.5"/><path d="M3.5 12h17M12 3.5c2.5 2.3 3.8 5.2 3.8 8.5s-1.3 6.2-3.8 8.5c-2.5-2.3-3.8-5.2-3.8-8.5s1.3-6.2 3.8-8.5z"/>',
  member: '<path d="M12 4 2.5 8.5 12 13l9.5-4.5L12 4z"/><path d="M6 10.7v5c1.7 1.6 3.7 2.4 6 2.4s4.3-.8 6-2.4v-5M21.5 8.5V14"/>',
  media: '<rect x="3.5" y="4.5" width="17" height="15" rx="2"/><circle cx="9" cy="9.5" r="1.6"/><path d="M3.5 16.5l4.5-4 4 3.5 3-2.5 5.5 4.5"/>',
  rep: '<path d="m12 3.5 2.6 5.3 5.9.9-4.3 4.1 1 5.8L12 16.9l-5.2 2.7 1-5.8-4.3-4.1 5.9-.9L12 3.5z"/>',
  report: '<path d="M4 20V4M4 20h16"/><path d="M8.5 16v-5M13 16V7.5M17.5 16v-3"/>',
  apps: '<path d="M12 3.2 15 6l-3 2.8L9 6l3-2.8zM6 9.2 9 12l-3 2.8L3 12l3-2.8zM18 9.2 21 12l-3 2.8L15 12l3-2.8zM12 15.2 15 18l-3 2.8L9 18l3-2.8z"/>',
  gear: '<circle cx="12" cy="12" r="3.2"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1a2 2 0 1 1-2.9 2.9l-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.5v.2a2 2 0 1 1-4.1 0V21a1.7 1.7 0 0 0-1.1-1.6 1.7 1.7 0 0 0-1.9.3l-.1.1a2 2 0 1 1-2.9-2.9l.1-.1a1.7 1.7 0 0 0 .3-1.9 1.7 1.7 0 0 0-1.5-1h-.2a2 2 0 1 1 0-4.1H3a1.7 1.7 0 0 0 1.6-1.1 1.7 1.7 0 0 0-.3-1.9l-.1-.1a2 2 0 1 1 2.9-2.9l.1.1a1.7 1.7 0 0 0 1.9.3H9a1.7 1.7 0 0 0 1-1.5v-.2a2 2 0 1 1 4.1 0V3a1.7 1.7 0 0 0 1 1.6 1.7 1.7 0 0 0 1.9-.3l.1-.1a2 2 0 1 1 2.9 2.9l-.1.1a1.7 1.7 0 0 0-.3 1.9v.1a1.7 1.7 0 0 0 1.5 1h.2a2 2 0 1 1 0 4.1H21a1.7 1.7 0 0 0-1.6 1z"/>',
  search: '<circle cx="11" cy="11" r="6.5"/><path d="m20 20-3.8-3.8"/>',
  chev: '<path d="m8.5 5 7 7-7 7"/>',
  chevd: '<path d="m6 9.5 6 6 6-6"/>',
  kebab: '<circle cx="12" cy="5.5" r="1.4" fill="currentColor" stroke="none"/><circle cx="12" cy="12" r="1.4" fill="currentColor" stroke="none"/><circle cx="12" cy="18.5" r="1.4" fill="currentColor" stroke="none"/>',
  send: '<path d="M21 3 3.5 10.2l6.8 2.9L13 20z M21 3l-10.7 10.1"/>',
  phone: '<path d="M22 16.9v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.6-3 19.5 19.5 0 0 1-6-6 19.8 19.8 0 0 1-3-8.7A2 2 0 0 1 4.1 2h3a2 2 0 0 1 2 1.7c.1 1 .4 2 .7 2.8a2 2 0 0 1-.4 2.1L8.1 9.9a16 16 0 0 0 6 6l1.3-1.3a2 2 0 0 1 2.1-.4c.9.3 1.9.5 2.8.7a2 2 0 0 1 1.7 2z"/>',
  mail: '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3.5 7 8.5 6 8.5-6"/>',
  check: '<path d="m4.5 12.5 5 5 10-11"/>',
  back: '<path d="M15.5 5l-7 7 7 7"/>',
  x: '<path d="M6 6l12 12M18 6 6 18"/>',
  clock: '<circle cx="12" cy="12" r="8.5"/><path d="M12 7v5.2l3.4 2"/>',
  sms: '<path d="M20.5 11.5a7.5 7.5 0 0 1-7.5 7.5c-1 0-2-.2-2.9-.6L5 20l1.6-4.1a7.5 7.5 0 1 1 13.9-4.4z"/>'
};
const ic = (name, s) => `<svg width="${s || 17}" height="${s || 17}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">${I[name] || ""}</svg>`;
const CH_ICON = { sms: "sms", email: "mail", call: "phone", fb: "convo", gmb: "sites" };
const CH_NAME = { sms: "SMS", email: "Email", call: "Call", fb: "Facebook", gmb: "Google" };

// ---- GHL sidebar structure ----
const NAV = [
  { id: "launchpad", label: "Launchpad", icon: "launchpad" },
  { id: "dashboard", label: "Dashboard", icon: "dash" },
  { id: "conversations", label: "Conversations", icon: "convo", badge: () => (D.conversations || []).reduce((s, c) => s + (c.unread || 0), 0) || null },
  { id: "calendars", label: "Calendars", icon: "cal" },
  { id: "contacts", label: "Contacts", icon: "contacts" },
  { id: "opportunities", label: "Opportunities", icon: "opps" },
  { id: "payments", label: "Payments", icon: "pay" },
  { id: "marketing", label: "Marketing", icon: "mktg" },
  { id: "automation", label: "Automation", icon: "auto" },
  { id: "sites", label: "Sites", icon: "sites" },
  { id: "memberships", label: "Memberships", icon: "member" },
  { id: "media", label: "Media Storage", icon: "media" },
  { id: "reputation", label: "Reputation", icon: "rep" },
  { id: "reporting", label: "Reporting", icon: "report" },
  { id: "apps", label: "App Marketplace", icon: "apps" }
];
const LIVE = { launchpad: 1, dashboard: 1, conversations: 1, calendars: 1, contacts: 1, opportunities: 1, payments: 1, reputation: 1 };
const TITLES = { launchpad: "Launchpad", dashboard: "Dashboard", conversations: "Conversations", calendars: "Calendars", contacts: "Contacts", opportunities: "Opportunities", payments: "Payments", marketing: "Marketing", automation: "Automation", sites: "Sites", memberships: "Memberships", media: "Media Storage", reputation: "Reputation", reporting: "Reporting", apps: "App Marketplace", settings: "Settings" };

function renderSidebar(active) {
  const item = n => `<a class="ni ${active === n.id ? "on" : ""}" href="#/${n.id}">${ic(n.icon)}<span>${esc(n.label)}</span>${n.badge && n.badge() ? `<span class="bdg">${n.badge()}</span>` : ""}</a>`;
  $("side").innerHTML = `
    <div class="loc" title="Sub-account">
      <div class="logo">BP</div>
      <div class="nm"><b>Bronco Painting</b><span>${esc(D.business.city)}</span></div>
      ${ic("chevd", 15)}
    </div>
    <div class="sidesearch">${ic("search", 14)}<input placeholder="Search" aria-label="Search"></div>
    <nav>
      ${NAV.map(item).join("")}
      <div class="navgrow"></div>
      ${item({ id: "settings", label: "Settings", icon: "gear" })}
    </nav>`;
}

// ---- derived metrics ----
function metrics() {
  const opps = D.opportunities;
  const inRange = o => (o.status === "open" ? o.created_days_ago : o.updated_days_ago) <= RANGE;
  const open = opps.filter(o => o.status === "open");
  const won = opps.filter(o => o.status === "won" && inRange(o));
  const lost = opps.filter(o => o.status === "lost" && inRange(o));
  const sum = a => a.reduce((s, o) => s + (o.value || 0), 0);
  const stages = D.pipeline.stages;
  const byStage = stages.map(s => { const a = open.filter(o => o.stage === s); return { stage: s, n: a.length, v: sum(a) }; });
  const src = {};
  opps.filter(o => o.created_days_ago <= RANGE || o.status !== "open" && inRange(o)).forEach(o => {
    const s = src[o.source] || (src[o.source] = { leads: 0, won: 0, lost: 0, openV: 0, wonV: 0 });
    s.leads++; if (o.status === "won") { s.won++; s.wonV += o.value; } else if (o.status === "lost") s.lost++; else s.openV += o.value;
  });
  return { open, won, lost, openV: sum(open), wonV: sum(won), lostV: sum(lost), byStage, src };
}

// ---- SVG donut ----
function donut(segs, size, stroke, center1, center2) {
  const r = (size - stroke) / 2, C = 2 * Math.PI * r, total = segs.reduce((s, x) => s + x.v, 0) || 1;
  let off = 0;
  const arcs = segs.filter(s => s.v > 0).map(s => {
    const len = s.v / total * C, gap = C - len;
    const el = `<circle r="${r}" cx="${size / 2}" cy="${size / 2}" fill="none" stroke="${s.c}" stroke-width="${stroke}"
      stroke-dasharray="${len - 2} ${gap + 2}" stroke-dashoffset="${-off}" stroke-linecap="round" transform="rotate(-90 ${size / 2} ${size / 2})"/>`;
    off += len; return el;
  }).join("");
  return `<svg width="${size}" height="${size}" viewBox="0 0 ${size} ${size}">
    <circle r="${r}" cx="${size / 2}" cy="${size / 2}" fill="none" stroke="var(--line)" stroke-width="${stroke}"/>${arcs}
    <text x="50%" y="${center2 ? "47%" : "52%"}" text-anchor="middle" class="dcenter" font-size="${size / 6.4}">${esc(center1)}</text>
    ${center2 ? `<text x="50%" y="62%" text-anchor="middle" class="dcenter2">${esc(center2)}</text>` : ""}</svg>`;
}
const legend = rows => `<div class="legend">${rows.map(r => `<div class="li"><span class="sw" style="background:${r.c}"></span><span class="ln">${esc(r.n)}</span><span class="lv">${r.v}</span></div>`).join("")}</div>`;
const wh = (title, sub) => `<div class="wh"><h3>${esc(title)}</h3>${sub ? `<span class="sub">${esc(sub)}</span>` : ""}<button class="kebab" aria-label="Widget menu">${ic("kebab", 15)}</button></div>`;
const STAGE_C = ["var(--st1)", "var(--st2)", "var(--st3)", "var(--st4)", "var(--st5)", "var(--st6)"];

// ---- views ----
function vDashboard() {
  const m = metrics();
  const convRate = m.won.length + m.lost.length ? Math.round(m.won.length / (m.won.length + m.lost.length) * 100) : 0;
  const maxStage = Math.max(...m.byStage.map(s => s.n), 1);
  const openTasks = D.tasks.filter(t => !t.done).sort((a, b) => a.due_in_days - b.due_in_days);
  const appts = D.appointments.slice().sort((a, b) => a.in_days - b.in_days || a.time.localeCompare(b.time));
  const wins = D.opportunities.filter(o => o.status === "won").sort((a, b) => a.updated_days_ago - b.updated_days_ago).slice(0, 5);
  const staff = Object.fromEntries(D.staff.map(s => [s.id, s.name]));
  const srcRows = Object.entries(m.src).sort((a, b) => (b[1].wonV + b[1].openV) - (a[1].wonV + a[1].openV));

  return `
  <div class="dhead">
    <h2>Dashboard</h2>
    <div class="dctl">
      <span class="sel">${ic("opps", 13)}<b>${esc(D.pipeline.name)}</b>${ic("chevd", 13)}</span>
      <label class="sel">${ic("cal", 13)}<select id="range" aria-label="Date range">
        <option value="7" ${RANGE === 7 ? "selected" : ""}>Last 7 days</option>
        <option value="30" ${RANGE === 30 ? "selected" : ""}>Last 30 days</option>
        <option value="90" ${RANGE === 90 ? "selected" : ""}>Last 90 days</option>
      </select></label>
      <button class="addw">+ Add Widget</button>
    </div>
  </div>
  <div class="grid">
    <div class="w s4">${wh("Opportunity Value", "last " + RANGE + "d")}
      <div class="donutwrap">
        ${donut([{ v: m.openV, c: "var(--gold)" }, { v: m.wonV, c: "var(--green)" }, { v: m.lostV, c: "var(--red)" }], 128, 13, moneyK(m.openV + m.wonV), "total pipeline")}
        ${legend([{ n: "Open", c: "var(--gold)", v: money(m.openV) }, { n: "Won", c: "var(--green)", v: money(m.wonV) }, { n: "Lost", c: "var(--red)", v: money(m.lostV) }])}
      </div></div>

    <div class="w s4">${wh("Conversion Rate", "won vs lost")}
      <div class="donutwrap">
        ${donut([{ v: m.won.length, c: "var(--green)" }, { v: m.lost.length, c: "var(--red)" }], 128, 13, convRate + "%", "win rate")}
        ${legend([{ n: "Won", c: "var(--green)", v: m.won.length + " (" + money(m.wonV) + ")" }, { n: "Lost", c: "var(--red)", v: m.lost.length + " (" + money(m.lostV) + ")" }])}
      </div></div>

    <div class="w s4">${wh("Manual Actions")}
      <div style="flex:1;display:flex;flex-direction:column;justify-content:center;gap:10px">
        <div class="big">${D.manual_actions.pending} <small>pending actions</small></div>
        <div class="mut" style="font-size:12px">Queued calls &amp; texts waiting in your follow-up campaigns.</div>
        <div><button class="cta">Let's start</button></div>
      </div></div>

    <div class="w s7">${wh("Funnel", "open opportunities by stage")}
      <div class="fun">${m.byStage.map(s => `
        <div class="frow"><span class="fn">${esc(s.stage)}</span>
          <span class="fbarw"><span class="fbar" style="width:${Math.max(10, s.n / maxStage * 100)}%">${s.n}</span></span>
          <span class="fv">${moneyK(s.v)}</span></div>`).join("")}
      </div></div>

    <div class="w s5">${wh("Stage Distribution", m.open.length + " open")}
      <div class="donutwrap">
        ${donut(m.byStage.map((s, i) => ({ v: s.n, c: STAGE_C[i % STAGE_C.length] })), 128, 13, String(m.open.length), "open opps")}
        ${legend(m.byStage.map((s, i) => ({ n: s.stage, c: STAGE_C[i % STAGE_C.length], v: s.n })))}
      </div></div>

    <div class="w s7">${wh("Lead Source Report", "last " + RANGE + "d")}
      <div class="repwrap"><table class="rep">
        <tr><th>Source</th><th>Leads</th><th>Won</th><th>Lost</th><th>Open $</th><th>Won $</th></tr>
        ${srcRows.map(([s, r]) => `<tr><td>${esc(s)}</td><td>${r.leads}</td><td style="color:${r.won ? "var(--green)" : "var(--faint)"}">${r.won}</td><td style="color:${r.lost ? "var(--red)" : "var(--faint)"}">${r.lost}</td><td>${moneyK(r.openV)}</td><td>${moneyK(r.wonV)}</td></tr>`).join("")}
      </table></div></div>

    <div class="w s5">${wh("Tasks", openTasks.length + " open")}
      ${openTasks.slice(0, 6).map(t => `
        <div class="task" data-task="${esc(t.id)}">
          <button class="tick" aria-label="Complete task"></button>
          <div class="grow"><div class="tt">${esc(t.title)}</div>
          <div class="tm ${t.due_in_days < 0 ? "due-over" : t.due_in_days === 0 ? "due-today" : ""}">${fmtDue(t.due_in_days)} · ${esc(staff[t.owner] || "")}</div></div>
        </div>`).join("") || '<div class="mut">No open tasks 🎉</div>'}
    </div>

    <div class="w s7">${wh("Upcoming Appointments", "next 10 days")}
      ${appts.slice(0, 5).map(a => `
        <div class="apr">
          <div class="apd"><b>${dIn(a.in_days).getDate()}</b><span>${MO[dIn(a.in_days).getMonth()]}</span></div>
          <div class="grow"><div class="ellip" style="font-weight:600">${esc(a.title)}</div>
            <div class="fnt mono" style="font-size:10.5px">${fmtIn(a.in_days)} · ${time12(a.time)} · ${a.duration_min}m</div></div>
          <span class="chip ${a.status === "confirmed" ? "g" : "a"}">${esc(a.status)}</span>
          <span class="chip">${esc(a.calendar)}</span>
        </div>`).join("")}
    </div>

    <div class="w s5">${wh("Recent Wins", money(m.wonV) + " last " + RANGE + "d")}
      ${wins.map(o => `
        <div class="trow"><span class="grow ellip">${esc(o.title)}</span>
          <span class="chip g">${moneyK(o.value)}</span><span class="fnt mono" style="font-size:10px">${fmtAgo(o.updated_days_ago)}</span></div>`).join("")}
    </div>
  </div>`;
}

function vOpportunities() {
  const m = metrics();
  const opps = D.opportunities.filter(o => OPP_FILTER === "all" ? true : o.status === OPP_FILTER);
  const contacts = Object.fromEntries(D.contacts.map(c => [c.id, c]));
  const seg = (id, label) => `<button class="segb ${OPP_FILTER === id ? "on" : ""}" data-of="${id}">${label}</button>`;
  const col = stage => {
    const a = opps.filter(o => o.stage === stage);
    const v = a.reduce((s, o) => s + o.value, 0);
    return `<div class="col" data-stage="${esc(stage)}"><div class="colh"><span class="cn">${esc(stage)}</span><span class="cc">${a.length}</span><span class="cv">${moneyK(v)}</span></div>
      ${a.map(o => `<div class="oc ${o.status}" data-contact="${esc(o.contact_id)}" ${o.status === "open" ? `draggable="true" data-opp="${esc(o.id)}"` : ""}>
        <div class="ot">${esc(o.title)}</div><div class="ov">${money(o.value)}</div>
        <div class="who">${esc((contacts[o.contact_id] || {}).name || "")}</div>
        <div class="om"><span class="chip">${esc(o.source)}</span>
          ${o.status === "won" ? '<span class="chip g">Won</span>' : o.status === "lost" ? '<span class="chip r">Lost</span>' : `<span class="chip">${fmtAgo(o.updated_days_ago) === "Just now" ? "today" : fmtAgo(o.updated_days_ago)}</span>`}
        </div></div>`).join("")}
    </div>`;
  };
  return `
  <div class="dhead"><h2>Opportunities</h2>
    <div class="dctl">
      <span class="sel">${ic("opps", 13)}<b>${esc(D.pipeline.name)}</b>${ic("chevd", 13)}</span>
      <span class="sel"><b>${money(m.openV)}</b>&nbsp;open · ${m.open.length} opps</span>
    </div></div>
  <div class="seg" style="margin-bottom:13px">${seg("open", "Open")}${seg("won", "Won")}${seg("lost", "Lost")}${seg("all", "All")}</div>
  <div class="board">${D.pipeline.stages.map(col).join("")}</div>
  <div class="mut" style="font-size:11px">Drag a card to another stage to move it — changes stick on this device.</div>`;
}

function vPayments() {
  const contacts = Object.fromEntries(D.contacts.map(c => [c.id, c]));
  const won = D.opportunities.filter(o => o.status === "won").sort((a, b) => a.updated_days_ago - b.updated_days_ago);
  const inv = won.map((o, i) => ({
    no: "INV-" + (1052 - i), o,
    st: o.updated_days_ago <= 7 ? "due" : o.updated_days_ago <= 14 ? "deposit" : "paid"
  }));
  const paidV = inv.reduce((s, x) => s + (x.st === "paid" ? x.o.value : x.st === "deposit" ? x.o.value / 2 : 0), 0);
  const outV = inv.reduce((s, x) => s + x.o.value, 0) - paidV;
  const stChip = st => st === "paid" ? '<span class="chip g">Paid</span>' : st === "deposit" ? '<span class="chip a">Deposit paid</span>' : '<span class="chip r">Due</span>';
  return `
  <div class="dhead"><h2>Payments</h2><div class="dctl"><button class="addw">+ New Invoice</button></div></div>
  <div class="grid">
    <div class="w s4">${wh("Collected", "last 90d")}<div class="big" style="color:var(--green)">${money(paidV)}</div><div class="mut" style="font-size:12px">across ${inv.length} invoices</div></div>
    <div class="w s4">${wh("Outstanding")}<div class="big" style="color:var(--amber)">${money(outV)}</div><div class="mut" style="font-size:12px">deposits &amp; balances due</div></div>
    <div class="w s4">${wh("Average Job")}<div class="big">${money(won.length ? won.reduce((s, o) => s + o.value, 0) / won.length : 0)}</div><div class="mut" style="font-size:12px">won jobs, trailing 90d</div></div>
    <div class="w s12">${wh("Invoices", inv.length + " total")}
      <div class="repwrap"><table class="rep">
        <tr><th>Invoice</th><th>Customer</th><th>Job</th><th>Issued</th><th>Amount</th><th>Status</th></tr>
        ${inv.map(x => `<tr><td class="mono">${esc(x.no)}</td>
          <td style="font-family:var(--sans);text-align:right;color:var(--txt)">${esc((contacts[x.o.contact_id] || {}).name || "—")}</td>
          <td style="font-family:var(--sans);text-align:right;color:var(--dim);max-width:200px;overflow:hidden;text-overflow:ellipsis">${esc(x.o.title)}</td>
          <td>${fmtAgo(x.o.updated_days_ago)}</td><td>${money(x.o.value)}</td><td>${stChip(x.st)}</td></tr>`).join("")}
      </table></div></div>
  </div>`;
}

function vReputation() {
  const rv = (D.reviews || []).slice().sort((a, b) => a.days_ago - b.days_ago);
  const avg = rv.length ? rv.reduce((s, r) => s + r.rating, 0) / rv.length : 0;
  const dist = [5, 4, 3, 2, 1].map(n => ({ n, c: rv.filter(r => r.rating === n).length }));
  const maxD = Math.max(...dist.map(d => d.c), 1);
  const star = f => `<svg width="13" height="13" viewBox="0 0 24 24" fill="${f ? "var(--gold)" : "none"}" stroke="${f ? "var(--gold)" : "var(--line2)"}" stroke-width="1.5" stroke-linejoin="round">${I.rep}</svg>`;
  const stars = n => Array.from({ length: 5 }, (_, i) => star(i < n)).join("");
  return `
  <div class="dhead"><h2>Reputation</h2><div class="dctl"><button class="addw">Send Review Request</button></div></div>
  <div class="grid">
    <div class="w s4">${wh("Average Rating")}
      <div style="display:flex;align-items:center;gap:12px"><div class="big">${avg.toFixed(1)}</div><div>${stars(Math.round(avg))}<div class="mut" style="font-size:11px;margin-top:3px">${rv.length} reviews · 90d</div></div></div></div>
    <div class="w s8">${wh("Rating Distribution")}
      ${dist.map(d => `<div style="display:flex;align-items:center;gap:10px;margin:5px 0">
        <span class="mono mut" style="font-size:11px;width:22px">${d.n}★</span>
        <div class="prog" style="flex:1;margin:0"><i style="width:${d.c / maxD * 100}%"></i></div>
        <span class="mono mut" style="font-size:11px;width:18px;text-align:right">${d.c}</span></div>`).join("")}
    </div>
    <div class="w s12">${wh("Latest Reviews")}
      ${rv.map(r => `
        <div class="trow" style="align-items:flex-start">
          <div class="pav" style="flex:0 0 auto">${initials(r.author)}</div>
          <div class="grow">
            <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap"><b style="font-size:12.5px">${esc(r.author)}</b>${stars(r.rating)}
              <span class="chip">${r.source === "google" ? "Google" : "Facebook"}</span>
              <span class="fnt mono" style="font-size:10px">${fmtAgo(r.days_ago)}</span></div>
            <div class="mut" style="font-size:12.5px;line-height:1.55;margin-top:4px">${esc(r.text)}</div>
          </div>
          ${r.replied ? '<span class="chip g" style="flex:0 0 auto">Replied</span>' : `<button class="cta ghost" style="flex:0 0 auto;padding:5px 12px;font-size:11px" data-rev="${esc(r.id)}">Reply</button>`}
        </div>`).join("")}
    </div>
  </div>`;
}

function vConversations() {
  const contacts = Object.fromEntries(D.contacts.map(c => [c.id, c]));
  let convs = D.conversations.slice().sort((a, b) => {
    const la = a.messages[a.messages.length - 1], lb = b.messages[b.messages.length - 1];
    return (la.days_ago * 24 - (la.hours_ago || 0)) - (lb.days_ago * 24 - (lb.hours_ago || 0));
  });
  if (CONV_FILTER === "unread") convs = convs.filter(c => c.unread > 0);
  if (!CONV_ID || !convs.find(c => c.id === CONV_ID)) CONV_ID = (convs[0] || {}).id || null;
  const cur = D.conversations.find(c => c.id === CONV_ID);
  const seg = (id, label) => `<button class="segb ${CONV_FILTER === id ? "on" : ""}" data-cf="${id}">${label}</button>`;
  const th = c => {
    const ct = contacts[c.contact_id] || {}, last = c.messages[c.messages.length - 1];
    return `<div class="ct ${c.id === CONV_ID ? "on" : ""} ${c.unread ? "unread" : ""}" data-conv="${esc(c.id)}">
      <div class="pav">${initials(ct.name)}<span class="ch">${ic(CH_ICON[c.channel] || "convo", 9)}</span></div>
      <div class="cm"><div class="cn1"><b>${esc(ct.name)}</b><span class="tm">${fmtAgo(last.days_ago, last.hours_ago)}</span></div>
      <div class="prev">${last.dir === "out" ? "You: " : ""}${esc(last.text)}</div></div>
      ${c.unread ? `<span class="un">${c.unread}</span>` : ""}</div>`;
  };
  const pane = !cur ? '<div class="noc">Select a conversation</div>' : (() => {
    const ct = contacts[cur.contact_id] || {};
    return `<div class="cph"><button class="back" data-back="1">${ic("back", 18)}</button>
      <div class="pav">${initials(ct.name)}</div>
      <div><b>${esc(ct.name)}</b><div class="sub2">${esc(CH_NAME[cur.channel] || cur.channel)} · ${esc(ct.phone || ct.email || "")}</div></div>
      <div class="topbtns"><button class="tbtn" title="Call">${ic("phone", 15)}</button><button class="tbtn" title="Email">${ic("mail", 15)}</button></div></div>
    <div class="msgs" id="msgs">${cur.messages.map(mm => `<div class="bub ${mm.dir}">${esc(mm.text)}<div class="bt">${fmtAgo(mm.days_ago, mm.hours_ago)}</div></div>`).join("")}</div>
    <div class="reply"><input id="replyIn" placeholder="Type a message… (demo)" aria-label="Reply"><button class="cta" id="replyBtn">${ic("send", 15)} Send</button></div>`;
  })();
  return `
  <div class="convo ${window.__chatOpen ? "chat" : ""}">
    <div class="clist">
      <div class="clh"><h3>Conversations</h3><div class="seg">${seg("all", "All")}${seg("unread", "Unread")}</div></div>
      <div class="cth">${convs.map(th).join("") || '<div class="noc" style="padding:30px">Nothing here</div>'}</div>
    </div>
    <div class="cpane">${pane}</div>
  </div>`;
}

function vContacts() {
  const q = CONTACT_Q.toLowerCase();
  const opps = D.opportunities;
  let list = D.contacts.filter(c =>
    (CONTACT_TYPE === "all" || c.type === CONTACT_TYPE) &&
    (!q || (c.name + " " + (c.email || "") + " " + (c.phone || "") + " " + (c.tags || []).join(" ")).toLowerCase().includes(q)));
  list = list.slice().sort((a, b) => a.last_activity_days_ago - b.last_activity_days_ago);
  const seg = (id, label) => `<button class="segb ${CONTACT_TYPE === id ? "on" : ""}" data-tf="${id}">${label}</button>`;
  return `
  <div class="dhead"><h2>Contacts</h2><div class="dctl"><button class="addw">+ Add Contact</button></div></div>
  <div class="ctool">
    <div class="csearch">${ic("search", 14)}<input id="cq" placeholder="Search name, email, phone, tag…" value="${esc(CONTACT_Q)}" aria-label="Search contacts"></div>
    <div class="seg">${seg("all", "All " + D.contacts.length)}${seg("lead", "Leads")}${seg("customer", "Customers")}</div>
  </div>
  <div class="ctable">
    <div class="crow2 hd"><span>Name</span><span>Phone</span><span class="hm">Email</span><span class="hm">Tags</span><span>Source</span><span class="hm">Last activity</span></div>
    ${list.map(c => `
      <div class="crow2" data-contact="${esc(c.id)}">
        <div class="cnm"><div class="pav">${initials(c.name)}</div><b>${esc(c.name)}</b></div>
        <span class="mono mut" style="font-size:11.5px">${esc(c.phone || "—")}</span>
        <span class="mut ellip hm" style="font-size:12px">${esc(c.email || "—")}</span>
        <span class="tags hm">${(c.tags || []).slice(0, 2).map(t => `<span class="chip">${esc(t)}</span>`).join("")}</span>
        <span class="chip gold" style="justify-self:start">${esc(c.source)}</span>
        <span class="fnt mono hm" style="font-size:10.5px">${fmtAgo(c.last_activity_days_ago)}</span>
      </div>`).join("") || '<div class="noc" style="padding:34px">No contacts match</div>'}
  </div>
  <div class="mut" style="margin-top:10px;font-size:11.5px">${list.length} of ${D.contacts.length} contacts</div>`;
}

function vCalendars() {
  const contacts = Object.fromEntries(D.contacts.map(c => [c.id, c]));
  const appts = D.appointments.slice().sort((a, b) => a.in_days - b.in_days || a.time.localeCompare(b.time));
  const groups = {};
  appts.forEach(a => (groups[a.in_days] = groups[a.in_days] || []).push(a));
  return `
  <div class="dhead"><h2>Calendars</h2>
    <div class="dctl"><span class="sel">${ic("cal", 13)}<b>All calendars</b>${ic("chevd", 13)}</span><button class="addw">+ New Appointment</button></div></div>
  <div class="grid">${Object.entries(groups).map(([d, list]) => `
    <div class="w s12" style="animation:none">
      <div class="wh"><h3>${fmtIn(Number(d))}</h3><span class="sub">${list.length} booked</span></div>
      ${list.map(a => `
        <div class="apr" data-contact="${esc(a.contact_id)}" style="cursor:pointer">
          <span class="mono" style="color:var(--gold);font-size:12px;width:74px;flex:0 0 auto">${time12(a.time)}</span>
          <div class="grow"><div style="font-weight:600;font-size:13px">${esc(a.title)}</div>
            <div class="fnt" style="font-size:11px">${esc((contacts[a.contact_id] || {}).address || "")}</div></div>
          <span class="chip">${esc(a.calendar)}</span>
          <span class="chip ${a.status === "confirmed" ? "g" : "a"}">${esc(a.status)}</span>
        </div>`).join("")}
    </div>`).join("")}
  </div>`;
}

function vLaunchpad() {
  const steps = [
    { t: "Connect your Google Business Profile", d: "Reviews, messages and call tracking flow into Bronco Painting.", ok: 1 },
    { t: "Connect Facebook & Instagram", d: "Lead ads and DMs land in Conversations automatically.", ok: 1 },
    { t: "Import your contacts", d: "34 contacts imported from your estimate spreadsheet.", ok: 1 },
    { t: "Set up your pipeline", d: '"Painting Jobs" — 6 stages from New Lead to In Production.', ok: 1 },
    { t: "Install the mobile app", d: "Run estimates and reply to leads from the truck.", ok: 0 },
    { t: "Connect payments", d: "Collect deposits on estimate approval.", ok: 0 }
  ];
  const done = steps.filter(s => s.ok).length;
  return `
  <div class="dhead"><h2>Launchpad</h2></div>
  <div class="lp"><div class="w s12" style="animation:none">
    <div class="wh"><h3>Get your account fully ramped</h3><span class="sub">${done}/${steps.length} complete</span></div>
    <div class="prog"><i style="width:${done / steps.length * 100}%"></i></div>
    ${steps.map(s => `
      <div class="lpi"><span class="st ${s.ok ? "ok" : "no"}">${s.ok ? ic("check", 12) : ""}</span>
        <div class="grow"><div style="font-weight:600;font-size:13px">${esc(s.t)}</div><div class="mut" style="font-size:12px">${esc(s.d)}</div></div>
        ${s.ok ? "" : '<button class="cta ghost">Set up</button>'}</div>`).join("")}
  </div></div>`;
}

function vPlaceholder(id) {
  const n = NAV.find(x => x.id === id) || { icon: "gear", label: TITLES[id] || id };
  return `<div class="empty">
    <div class="eic">${ic(n.icon, 30)}</div>
    <h3>${esc(TITLES[id] || n.label)}</h3>
    <p>This area mirrors the full platform's <b>${esc(TITLES[id] || n.label)}</b> section. The Bronco demo covers Dashboard, Opportunities, Conversations, Contacts, Calendars, Payments and Reputation — this space is reserved for the next build phase.</p>
    <a class="cta" href="#/dashboard" style="text-decoration:none">Back to Dashboard</a>
  </div>`;
}

// ---- contact slide-over ----
function openContact(cid) {
  const c = D.contacts.find(x => x.id === cid); if (!c) return;
  const opps = D.opportunities.filter(o => o.contact_id === cid);
  const conv = D.conversations.find(v => v.contact_id === cid);
  $("panel").innerHTML = `
    <div class="ph"><div class="pav">${initials(c.name)}</div>
      <div><b style="font-size:15px">${esc(c.name)}</b>
        <div class="fnt mono" style="font-size:10.5px">${esc(c.type)} · added ${fmtAgo(c.created_days_ago)}</div></div>
      <button class="x" id="pclose">${ic("x", 18)}</button></div>
    <div class="pbody">
      <div style="display:flex;gap:8px;margin-bottom:14px">
        <button class="cta ghost" style="flex:1;justify-content:center">${ic("phone", 14)} Call</button>
        <button class="cta ghost" style="flex:1;justify-content:center">${ic("sms", 14)} Text</button>
        <button class="cta ghost" style="flex:1;justify-content:center">${ic("mail", 14)} Email</button>
      </div>
      <div class="pkv"><span class="k">Phone</span><span class="v">${esc(c.phone || "—")}</span></div>
      <div class="pkv"><span class="k">Email</span><span class="v">${esc(c.email || "—")}</span></div>
      <div class="pkv"><span class="k">Address</span><span class="v" style="font-size:11px">${esc(c.address || "—")}</span></div>
      <div class="pkv"><span class="k">Source</span><span class="v">${esc(c.source)}</span></div>
      <div class="pkv"><span class="k">Tags</span><span class="v"><span class="tags" style="justify-content:flex-end">${(c.tags || []).map(t => `<span class="chip">${esc(t)}</span>`).join("")}</span></span></div>
      <div class="psec">Opportunities (${opps.length})</div>
      ${opps.map(o => `<div class="trow"><span class="grow ellip">${esc(o.title)}</span>
        <span class="chip ${o.status === "won" ? "g" : o.status === "lost" ? "r" : "gold"}">${o.status === "open" ? esc(o.stage) : esc(o.status)}</span>
        <span class="mono" style="font-size:12px">${moneyK(o.value)}</span></div>`).join("") || '<div class="mut" style="font-size:12px">None yet</div>'}
      ${conv ? `<div class="psec">Latest conversation</div>
        <div class="trow" style="cursor:pointer" id="pconv"><span class="grow ellip mut">${esc(conv.messages[conv.messages.length - 1].text)}</span>${ic("chev", 13)}</div>` : ""}
    </div>`;
  $("panel").classList.add("open"); $("scrim").classList.add("on");
  $("pclose").onclick = closePanel;
  const pc = $("pconv"); if (pc) pc.onclick = () => { closePanel(); CONV_ID = conv.id; location.hash = "#/conversations"; render(); };
}
function closePanel() { $("panel").classList.remove("open"); $("scrim").classList.remove("on"); }

// ---- router ----
function view() { return (location.hash.replace(/^#\//, "") || "dashboard").split("?")[0]; }
function render() {
  if (!D) return;
  const v = view();
  renderSidebar(v);
  $("crumb").textContent = TITLES[v] || "Dashboard";
  document.title = (TITLES[v] || "Dashboard") + " — Bronco Painting";
  const el = $("view");
  if (v === "dashboard") el.innerHTML = vDashboard();
  else if (v === "opportunities") el.innerHTML = vOpportunities();
  else if (v === "conversations") el.innerHTML = vConversations();
  else if (v === "contacts") el.innerHTML = vContacts();
  else if (v === "calendars") el.innerHTML = vCalendars();
  else if (v === "payments") el.innerHTML = vPayments();
  else if (v === "reputation") el.innerHTML = vReputation();
  else if (v === "launchpad") el.innerHTML = vLaunchpad();
  else el.innerHTML = vPlaceholder(v);
  el.scrollTop = 0;
  $("side").classList.remove("open"); $("scrim").classList.remove("on");
  wire(v);
}

function wire(v) {
  const el = $("view");
  if (v === "dashboard") {
    const r = $("range"); if (r) r.onchange = () => { RANGE = Number(r.value); render(); };
    el.querySelectorAll(".task .tick").forEach(btn => btn.onclick = e => {
      const row = e.currentTarget.closest(".task"); const t = D.tasks.find(x => x.id === row.dataset.task);
      if (t) t.done = !t.done; row.classList.toggle("done", t && t.done); e.currentTarget.classList.toggle("done", t && t.done);
      e.currentTarget.innerHTML = t && t.done ? ic("check", 11) : "";
    });
  }
  if (v === "opportunities") {
    el.querySelectorAll("[data-of]").forEach(b => b.onclick = () => { OPP_FILTER = b.dataset.of; render(); });
    el.querySelectorAll(".oc[data-contact]").forEach(c => c.onclick = () => openContact(c.dataset.contact));
    // drag & drop between stage columns; the move is kept per-device in localStorage
    let dragging = false;
    el.querySelectorAll(".oc[draggable]").forEach(c => {
      c.addEventListener("dragstart", e => { dragging = true; e.dataTransfer.setData("text/plain", c.dataset.opp); e.dataTransfer.effectAllowed = "move"; c.style.opacity = .4; });
      c.addEventListener("dragend", () => { c.style.opacity = ""; setTimeout(() => dragging = false, 50); });
      c.addEventListener("click", e => { if (dragging) e.stopImmediatePropagation(); }, true);
    });
    el.querySelectorAll(".col").forEach(colEl => {
      colEl.addEventListener("dragover", e => { e.preventDefault(); e.dataTransfer.dropEffect = "move"; colEl.classList.add("over"); });
      colEl.addEventListener("dragleave", () => colEl.classList.remove("over"));
      colEl.addEventListener("drop", e => {
        e.preventDefault(); colEl.classList.remove("over");
        const o = D.opportunities.find(x => x.id === e.dataTransfer.getData("text/plain"));
        const stage = colEl.dataset.stage;
        if (!o || !stage || o.stage === stage) return;
        o.stage = stage; o.updated_days_ago = 0;
        const ov = JSON.parse(localStorage.getItem("bronco-stages") || "{}");
        ov[o.id] = stage; localStorage.setItem("bronco-stages", JSON.stringify(ov));
        render();
      });
    });
  }
  if (v === "reputation") {
    el.querySelectorAll("[data-rev]").forEach(b => b.onclick = () => {
      const r = (D.reviews || []).find(x => x.id === b.dataset.rev);
      if (r) { r.replied = true; render(); }
    });
  }
  if (v === "conversations") {
    el.querySelectorAll("[data-cf]").forEach(b => b.onclick = () => { CONV_FILTER = b.dataset.cf; window.__chatOpen = false; render(); });
    el.querySelectorAll("[data-conv]").forEach(t => t.onclick = () => {
      CONV_ID = t.dataset.conv; window.__chatOpen = true;
      const c = D.conversations.find(x => x.id === CONV_ID); if (c) c.unread = 0;
      render();
    });
    const back = el.querySelector("[data-back]"); if (back) back.onclick = () => { window.__chatOpen = false; render(); };
    const msgs = $("msgs"); if (msgs) msgs.scrollTop = msgs.scrollHeight;
    const btn = $("replyBtn"), inp = $("replyIn");
    const send = () => {
      const txt = (inp.value || "").trim(); if (!txt) return;
      const c = D.conversations.find(x => x.id === CONV_ID); if (!c) return;
      c.messages.push({ dir: "out", text: txt, days_ago: 0, hours_ago: 0 });
      render();
    };
    if (btn) btn.onclick = send;
    if (inp) inp.onkeydown = e => { if (e.key === "Enter") send(); };
  }
  if (v === "contacts") {
    const q = $("cq");
    if (q) { q.oninput = () => { CONTACT_Q = q.value; render(); const q2 = $("cq"); q2.focus(); q2.setSelectionRange(q2.value.length, q2.value.length); }; }
    el.querySelectorAll("[data-tf]").forEach(b => b.onclick = () => { CONTACT_TYPE = b.dataset.tf; render(); });
    el.querySelectorAll(".crow2[data-contact]").forEach(r => r.onclick = () => openContact(r.dataset.contact));
  }
  if (v === "calendars") {
    el.querySelectorAll(".apr[data-contact]").forEach(r => r.onclick = () => openContact(r.dataset.contact));
  }
}

async function boot() {
  try { D = await (await fetch("bronco.json?_=" + Date.now(), { cache: "no-store" })).json(); }
  catch (e) { $("view").innerHTML = '<div class="empty"><h3>Couldn\'t load data</h3><p>bronco.json is missing or invalid.</p></div>'; return; }
  // replay this device's kanban moves (only onto valid, still-open opportunities)
  try {
    const ov = JSON.parse(localStorage.getItem("bronco-stages") || "{}");
    D.opportunities.forEach(o => { if (o.status === "open" && ov[o.id] && D.pipeline.stages.includes(ov[o.id])) o.stage = ov[o.id]; });
  } catch (e) {}
  render();
}
window.addEventListener("hashchange", render);
$("themeBtn").onclick = () => {
  const on = document.body.classList.toggle("ghl");
  localStorage.setItem("bronco-theme", on ? "ghl" : "dark");
  render();
};
$("burger").onclick = () => { $("side").classList.toggle("open"); $("scrim").classList.toggle("on", $("side").classList.contains("open")); };
$("scrim").onclick = () => { closePanel(); $("side").classList.remove("open"); $("scrim").classList.remove("on"); };
if ("serviceWorker" in navigator) navigator.serviceWorker.register("sw.js").catch(() => {});
boot();
