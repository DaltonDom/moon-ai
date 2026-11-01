// moon-ai dashboard: plain JavaScript, no build step, so the Mac needs no Node.
// Reads /api/* (src/moon_ai/dashboard/api.py). Every value from the API is escaped.
"use strict";

// ---------- helpers ----------
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const usd = (x, sign = true) => x == null ? "–" : (x < 0 ? "−" : sign && x > 0 ? "+" : "") + "$" + Math.abs(Math.round(x)).toLocaleString("en-US");
const pct = (x) => x == null ? "–" : Math.round(x * 100) + "%";
const T = (label, tip) => `<span class="term" tabindex="0" data-tip="${esc(tip)}">${label}</span>`;
const ny = (iso, opts) => new Date(iso).toLocaleString("en-US", { timeZone: "America/New_York", ...opts });
const nyTime = (iso) => ny(iso, { hour: "numeric", minute: "2-digit" });
const nyDay = (iso) => ny(iso, { month: "short", day: "numeric" });
const tradeHref = (id) => "#trade/" + encodeURIComponent(id);

async function api(path, opts = {}) {
  const r = await fetch("/api/" + path, opts);
  if (!r.ok) {
    let msg = r.statusText;
    try { msg = (await r.json()).detail || msg; } catch (_) { /* not JSON */ }
    const e = new Error(msg); e.status = r.status; throw e;
  }
  return (r.headers.get("content-type") || "").includes("json") ? r.json() : r.text();
}
const post = (path, body) => api(path, { method: "POST", headers: { "X-Moon-AI": "1", "Content-Type": "application/json" }, body: body ? JSON.stringify(body) : undefined });

function toast(msg) {
  const t = document.createElement("div"); t.className = "toast"; t.textContent = msg; t.setAttribute("role", "status");
  document.body.append(t); setTimeout(() => t.remove(), 4000);
}

const TIPS = {
  pf: "Profit factor: dollars won for every $1 lost. Above $1 makes money; we need $1.30 or more.",
  dd: "The biggest drop from a high point before recovering, as a share of the account. Prop firms fail you past their limit; we need under 10%.",
  R: "R is the amount risked on one trade. +2R means the trade made twice what it risked.",
  random: "We compare each setup with trades taken at random times in the same window, with the same stop and target. A real setup must clearly beat random.",
  luck: "We test several versions of each idea, so some look good by chance. This is how sure we are the result is real, after allowing for every version tried. Needs 95%.",
  conf: "How likely the model thinks this trade will hit its target. It only takes trades where this beats the break-even level for the trade's reward-to-risk.",
  stress: "The same backtest with slippage doubled. A real edge survives worse fills.",
};
const BUCKETS = {
  rule_break: "Rule break or execution error", good_won: "Good setup, won", good_lost: "Good setup, unlucky loss",
  bad_won: "Bad setup, lucky win", bad_lost: "Bad setup, lost",
};
const bucketWord = (b) => BUCKETS[b] || b;
const SKIPS = {
  "skipped:ml": "low confidence", "skipped:blackout": "during news", "skipped:cap": "already 2 trades that session",
  "skipped:daily_stop": "daily loss limit hit", "skipped:london_min_stop": "stop too small", "skipped:session": "outside trading hours",
  "skipped:busy": "already in a trade", "skipped:kill_switch": "kill switch on", "skipped:size": "too big to size", unfilled: "price never reached the entry",
};
const STEP_WORDS = { preflight: "Ready check", pull: "Get data", check: "Check data", news: "News calendar", replay: "Paper trades", reviews: "Claude reviews", models: "Model check", housekeeping: "Backup", summary: "Summary" };
const MARK = { ok: ["ok", "✓"], warn: ["wait", "!"], skipped: ["wait", "–"], fail: ["no", "✕"] };

function ring(frac, color, size = 64, label = "") {
  const r = size / 2 - 6, c = 2 * Math.PI * r, f = Math.max(0, Math.min(1, frac || 0));
  return `<svg width="${size}" height="${size}" viewBox="0 0 ${size} ${size}" role="img" aria-label="${Math.round(f * 100)}%"><circle cx="${size / 2}" cy="${size / 2}" r="${r}" fill="none" stroke="var(--line)" stroke-width="7"/>
    <circle cx="${size / 2}" cy="${size / 2}" r="${r}" fill="none" stroke="var(${color})" stroke-width="7" stroke-linecap="round" stroke-dasharray="${c * f} ${c}" transform="rotate(-90 ${size / 2} ${size / 2})"/>
    <text x="50%" y="54%" text-anchor="middle" style="font:700 ${size > 80 ? 22 : 13}px var(--num);fill:var(--ink)">${label}</text></svg>`;
}
function spark(vals, w = 160, h = 40) {
  if (vals.length < 2) return "";
  const lo = Math.min(0, ...vals), hi = Math.max(1, ...vals), x = (i) => i / (vals.length - 1) * w, y = (v) => 4 + (hi - v) / (hi - lo) * (h - 8);
  const d = vals.map((v, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join("");
  return `<svg width="100%" height="${h}" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" aria-hidden="true"><line x1="0" x2="${w}" y1="${y(0)}" y2="${y(0)}" stroke="var(--line)" stroke-dasharray="3 3"/><path d="${d}" fill="none" stroke="var(${vals.at(-1) >= 0 ? "--win" : "--loss"})" stroke-width="2" vector-effect="non-scaling-stroke"/></svg>`;
}

// ---------- charts ----------
let EQ = [];
function equity(pts) {
  EQ = pts;
  if (pts.length < 2) return `<p class="empty">The chart appears after the second paper trade.</p>`;
  const W = 900, H = 300, L = 62, Rt = 12, top = 14, mainH = 190, gap = 18, ddH = 50;
  const lo = Math.min(0, ...pts.map((p) => p.profit_usd)), hi = Math.max(100, ...pts.map((p) => p.profit_usd)) * 1.05;
  const x = (i) => L + i / (pts.length - 1) * (W - L - Rt), y = (v) => top + (hi - v) / (hi - lo) * mainH;
  const dmin = Math.min(-1, ...pts.map((p) => p.dip_usd)), yd = (v) => top + mainH + gap + v / dmin * ddH;
  const line = pts.map((p, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(p.profit_usd).toFixed(1)}`).join("");
  const area = line + `L${x(pts.length - 1)},${y(lo)}L${x(0)},${y(lo)}Z`;
  const dd = `M${x(0)},${yd(0)}` + pts.map((p, i) => `L${x(i).toFixed(1)},${yd(p.dip_usd).toFixed(1)}`).join("") + `L${x(pts.length - 1)},${yd(0)}Z`;
  const span = hi - lo, step = [250, 500, 1000, 2500, 5000, 10000, 25000].find((s) => span / s <= 6) || 50000, g = [];
  for (let v = Math.ceil(lo / step) * step; v <= hi; v += step) g.push(`<line x1="${L}" x2="${W - Rt}" y1="${y(v)}" y2="${y(v)}" stroke="var(--line)"/><text x="${L - 8}" y="${y(v) + 4}" text-anchor="end">${usd(v, false)}</text>`);
  const months = []; let lastM = "";
  pts.forEach((p, i) => { const m = ny(p.t, { month: "short" }); if (m !== lastM) { lastM = m; months.push(`<text x="${x(i)}" y="${H - 4}">${m}</text>`); } });
  return `<div class="chartwrap" style="overflow-x:auto"><svg id="eqsvg" viewBox="0 0 ${W} ${H}" width="100%" style="min-width:620px" role="img" aria-label="Paper account growth and dips">
    <defs><linearGradient id="gfill" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="var(--accent)" stop-opacity=".28"/><stop offset="1" stop-color="var(--accent)" stop-opacity="0"/></linearGradient></defs>
    ${g.join("")}<path d="${area}" fill="url(#gfill)"/><path d="${line}" fill="none" stroke="var(--accent)" stroke-width="2.5" stroke-linejoin="round"/>
    <circle cx="${x(pts.length - 1)}" cy="${y(pts.at(-1).profit_usd)}" r="5" fill="var(--accent)" stroke="var(--card)" stroke-width="2"/>
    <text x="${L - 8}" y="${top + mainH + gap + 4}" text-anchor="end">dips</text>
    <path d="${dd}" fill="var(--loss-soft)" stroke="var(--loss)" stroke-width="1.2"/>
    <text x="${L - 8}" y="${yd(dmin) + 4}" text-anchor="end">${usd(dmin)}</text>
    ${months.join("")}
    <line id="hov" x1="0" x2="0" y1="${top}" y2="${top + mainH}" stroke="var(--sub)" stroke-dasharray="3 3" visibility="hidden"/>
  </svg></div>`;
}
function calendar(days) {
  if (!days.length) return `<p class="empty">No trading days yet.</p>`;
  const byDay = Object.fromEntries(days.map((d) => [d.day, d]));
  const cells = []; let d = new Date(days[0].day + "T12:00:00Z"); const end = new Date(days.at(-1).day + "T12:00:00Z");
  while (d <= end) {
    if (![0, 6].includes(d.getUTCDay())) {
      const k = d.toISOString().slice(0, 10), v = byDay[k];
      const bg = !v ? "var(--line)" : v.net_usd > 0 ? `color-mix(in srgb, var(--win) ${Math.min(100, 35 + v.net_usd / 12)}%, transparent)` : `color-mix(in srgb, var(--loss) ${Math.min(100, 35 - v.net_usd / 12)}%, transparent)`;
      cells.push(`<span style="background:${bg}" data-tip="${k}: ${v ? `${usd(v.net_usd)} from ${v.trades} trade${v.trades === 1 ? "" : "s"}` : "no trades"}"></span>`);
    }
    d = new Date(d.getTime() + 864e5);
  }
  return `<div class="cal">${cells.join("")}</div>`;
}
function tradeRow(t, max) {
  const w = Math.min(50, Math.abs(t.net_usd || 0) / max * 50), up = (t.net_usd || 0) >= 0;
  return `<a class="trow" href="${tradeHref(t.candidate_id)}"><span class="sub num" style="font-size:13px">${nyDay(t.entry_time)}</span>
    <span><b>${esc(t.setup_title)}</b><br><span class="sub" style="font-size:13px">${t.side === "long" ? "Long" : "Short"} · ${t.open ? "still open" : esc(bucketWord(t.review))}</span></span>
    <span class="barcell"><i style="${up ? `left:50%;width:${w}%;background:var(--win)` : `right:50%;width:${w}%;background:var(--loss)`}"></i></span>
    <span class="num ${up ? "win" : "loss"}" style="text-align:right;font-weight:600">${t.open ? "open" : usd(t.net_usd)}</span></a>`;
}

// ---------- views ----------
const VIEWS = {};

VIEWS.today = async () => {
  const d = await api("today"), s = d.stats, g = Object.fromEntries(d.goals.map((x) => [x.key, x]));
  const goals = [
    { t: "Number of trades", v: `${s.trades}`, need: "need 200", f: s.trades / 200, ok: g.trades.ok, e: g.trades.ok ? "Done" : `${200 - s.trades} more to go` },
    { t: "Time on paper", v: `${g.months.value} mo`, need: "need 3 months", f: g.months.value / 3, ok: g.months.ok, e: g.months.ok ? "Done" : "Counting from the first paper trade" },
    { t: T("Profit factor", TIPS.pf), v: s.profit_factor == null ? "–" : `$${s.profit_factor.toFixed(2)}`, need: "need $1.30+", f: (s.profit_factor || 0) / 1.3, ok: g.profit_factor.ok, e: s.profit_factor == null ? "No losses yet to compare" : `Won $${s.profit_factor.toFixed(2)} for every $1 lost` },
    { t: T("Biggest dip", TIPS.dd), v: `${s.max_dip_pct.toFixed(1)}%`, need: "must stay under 10%", f: s.trades ? 1 - s.max_dip_pct / 10 : 0, ok: g.max_dip_pct.ok, e: s.trades ? `Worst drop was ${usd(-s.max_dip_usd)} from a high` : "No trades yet" },
  ];
  const met = d.goals_met, missing = goals.filter((x) => !x.ok).map((x) => x.t.replace(/<[^>]+>/g, "").toLowerCase());
  return `<div class="stack">
    <section class="card"><div class="hero">${ring(met / 4, met === 4 ? "--win" : "--accent", 120, `${met}/4`)}
      <div style="display:grid;gap:8px"><span class="eyebrow">Ready to go live?</span>
      <h1>${met === 4 ? "Ready to trade for real." : `Not yet: ${met} of 4 goals met.`}</h1>
      <p class="lead">The bot must meet all four goals in paper trading before we pay for a prop-firm evaluation. It's ${s.net_usd >= 0 ? "up" : "down"} <b class="${s.net_usd >= 0 ? "win" : "loss"}">${usd(s.net_usd)}</b> on a ${usd(d.account_usd, false)} paper account.${missing.length ? ` Still missing: ${esc(missing.join(", "))}.` : ""}</p></div></div>
      <div class="goals">${goals.map((x) => `<div class="goal">${ring(x.f, x.ok ? "--win" : "--amber", 64, x.ok ? "✓" : pct(Math.max(0, Math.min(1, x.f))))}
        <div><span class="t">${x.t}</span><b class="${x.ok ? "win" : ""}">${x.v}</b><span class="explain">${x.need} · ${x.e}</span></div></div>`).join("")}</div>
    </section>
    <div class="row">${lastNight(d.last_night)}${needsYou(d.needs_you)}</div>
    <section class="card"><div class="btns" style="justify-content:space-between"><span class="eyebrow">Paper account growth</span>
      <span class="legend"><span><i style="background:var(--accent)"></i>profit so far</span><span><i style="background:var(--loss)"></i>dips below the last high</span></span></div>
      ${equity(d.equity)}
      <p class="explain" id="hovtxt">Hover the chart to see any trade. Each trade risks 1% of the account, called ${T("1R", TIPS.R)}.</p></section>
    <div class="row">
      <section class="card"><span class="eyebrow">Every trading day</span>${calendar(d.calendar)}
        <span class="legend"><span><i style="background:var(--win)"></i>profit day</span><span><i style="background:var(--loss)"></i>loss day</span><span><i style="background:var(--line)"></i>no trade</span></span></section>
      ${winsVsLosses(s)}
    </div></div>`;
};

function lastNight(n) {
  if (!n) return `<section class="card night"><span class="eyebrow">Last night</span><p class="empty">No nightly run yet. On the Mac, run <code>uv run moon-ai nightly install</code>.</p></section>`;
  const bad = n.status === "fail", skipped = Object.entries(n.skipped), nskip = skipped.reduce((a, [, v]) => a + v, 0);
  const closed = n.trades.filter((t) => !t.open);
  return `<section class="card night"><div class="nighthead"><span class="eyebrow">Last night · ${esc(n.sessions.map((s) => s.slice(5).replace("-", "/")).join(", ") || nyDay(n.ran_at))}</span>
      <span class="okline ${bad ? "bad" : ""}"><span class="okdot"></span>Ran at ${nyTime(n.ran_at)} · ${bad ? "a step failed" : "all steps OK"}</span></div>
    <div class="nightsum"><b class="num ${n.net_usd >= 0 ? "win" : "loss"}">${usd(n.net_usd)}</b><span class="sub">from ${closed.length} trade${closed.length === 1 ? "" : "s"}</span></div>
    <div class="nlist">
      ${n.trades.map((t) => `<a class="ntrade" href="${tradeHref(t.candidate_id)}"><span class="side ${t.open ? "sub" : t.net_usd >= 0 ? "win" : "loss"}">${t.open ? "OPEN" : t.net_usd >= 0 ? "WIN" : "LOSS"}</span>
        <span class="nmain"><b>${esc(t.setup_title)}</b><span class="sub">${t.side === "long" ? "Long" : "Short"} · ${nyTime(t.entry_time)} · ${esc(bucketWord(t.review))}</span></span>
        <span class="num ${(t.net_usd || 0) >= 0 ? "win" : "loss"} namt">${t.open ? "" : usd(t.net_usd)}</span></a>`).join("")}
      ${nskip ? `<div class="ntrade skip"><span class="side sub">SKIP</span><span class="nmain"><b>${nskip} setup${nskip === 1 ? "" : "s"} skipped</b><span class="sub">${esc(skipped.map(([k, v]) => `${v} ${SKIPS[k] || k}`).join(", "))}</span></span><span></span></div>` : ""}
      ${!n.trades.length && !nskip ? `<p class="explain">No setups appeared in that session.</p>` : ""}
    </div>
    <details><summary>Each step</summary><div class="steplist" style="margin-top:8px">${n.steps.map((s) => { const [cls, m] = MARK[s.status] || ["wait", "?"]; return `<div><span class="mark ${cls}" style="width:20px;height:20px;border-radius:50%;display:grid;place-items:center;font-size:11px">${m}</span><b>${esc(STEP_WORDS[s.step] || s.step)}</b><span class="sub">${esc(s.message)}</span></div>`; }).join("")}</div></details>
  </section>`;
}

function needsYou(items) {
  const ICON = { proposal: ["?", "accent"], review: ["!", "amber"], stale: ["!", "loss"], fail: ["✕", "loss"], setup: ["→", "accent"] };
  const LINK = { proposal: "#changes", review: "#trades", stale: "#today", fail: "#today", setup: "#today" };
  return `<section class="card"><span class="eyebrow">Needs you</span><div class="todo">
    ${items.length ? items.map((i) => { const [ic, col] = ICON[i.kind] || ["!", "amber"]; return `<a href="${LINK[i.kind] || "#today"}"><span class="ico" style="background:var(--${col}-soft);color:var(--${col})">${ic}</span><span><b>${esc(i.title)}</b><br><span class="sub" style="font-size:13px">${esc(i.detail)}</span></span><span class="go">${i.kind === "proposal" ? "Review →" : ""}</span></a>`; }).join("")
      : `<p class="empty">Nothing. The bot is running on its own.</p>`}
  </div></section>`;
}

function winsVsLosses(s) {
  if (!s.trades) return `<section class="card"><span class="eyebrow">Wins vs losses</span><p class="empty">No closed trades yet.</p></section>`;
  const mx = Math.max(s.avg_win_usd || 0, -(s.avg_loss_usd || 0), 1);
  const ratio = s.avg_win_usd && s.avg_loss_usd ? s.avg_win_usd / -s.avg_loss_usd : null;
  const story = ratio == null ? "" : s.win_rate < 0.5 && ratio > 1 ? `It wins fewer than half its trades, but each win is about ${ratio.toFixed(1)}× the size of a loss.` : `Wins are about ${ratio.toFixed(1)}× the size of losses.`;
  return `<section class="card"><span class="eyebrow">Wins vs losses</span><div class="vs">
      <div class="vsbar"><span>Wins: ${s.wins} of ${s.trades}</span><span class="track"><i style="width:${pct(s.win_rate)};background:var(--win)"></i></span><span class="num">${pct(s.win_rate)}</span></div>
      <div class="vsbar"><span>Avg win</span><span class="track"><i style="width:${(s.avg_win_usd || 0) / mx * 100}%;background:var(--win)"></i></span><span class="num win">${usd(s.avg_win_usd)}</span></div>
      <div class="vsbar"><span>Avg loss</span><span class="track"><i style="width:${-(s.avg_loss_usd || 0) / mx * 100}%;background:var(--loss)"></i></span><span class="num loss">${usd(s.avg_loss_usd)}</span></div>
    </div><p class="explain">${story} ${s.net_usd >= 0 ? "That's why it makes money." : "So far that isn't enough to make money."}</p>
    <details><summary>Advanced numbers</summary><div class="adv">
      <div><span>Average per trade <span class="sub">(in R)</span></span><b class="num">${s.advanced.expectancy_r == null ? "–" : s.advanced.expectancy_r.toFixed(2) + "R"}</b></div>
      <div><span>Sharpe <span class="sub">(steadiness of returns; above 1 is good)</span></span><b class="num">${s.advanced.sharpe.toFixed(2)}</b></div>
      <div><span>Sortino <span class="sub">(like Sharpe, but only counts the bad swings)</span></span><b class="num">${s.advanced.sortino.toFixed(2)}</b></div>
    </div></details></section>`;
}

const VERDICT = {
  "go-forward": ["Passed its tests", "win", "Taking paper trades."],
  retired: ["Retired", "loss", "Didn't pass, even after its pre-registered retests; switched off."],
  insufficient: ["Not enough trades yet", "amber", "Needs 100 backtest trades before we can judge it."],
  null: ["Not tested yet", "sub", "Run `moon-ai backtest --all` on the Mac to test it."],
};

VIEWS.setups = async () => {
  const [rows, jobs] = await Promise.all([api("setups"), api("backtests")]);
  const chk = (ok, title, detail) => `<div class="chk"><span class="mark ${ok == null ? "wait" : ok ? "ok" : "no"}">${ok == null ? "…" : ok ? "✓" : "✕"}</span><span>${title}</span><span class="sub num" style="font-size:13px">${esc(detail)}</span></div>`;
  const running = jobs.filter((j) => j.state === "queued" || j.state === "running");
  return `<div class="stack"><div><h2>Setups</h2><p class="lead">Each setup is one ICT pattern the bot looks for. A setup only trades once it passes all four checks on years of history.</p></div>
    ${running.length ? `<section class="card"><span class="eyebrow">Backtests running</span><div class="joblist">${running.map((j) => `<div>${esc(j.setup)} · ${esc(j.start)} to ${esc(j.end)} · <b>${esc(j.state)}</b></div>`).join("")}</div><p class="explain">Refresh in a few minutes. The report card opens from here when it's done.</p></section>` : ""}
    <div class="row">${rows.map((s) => {
      const [lab, cls, why] = VERDICT[s.verdict] || VERDICT.null, c = s.checks || {}, risk = s.risk_per_trade_usd, p = s.paper;
      const edgeUsd = c.edge_r == null ? null : c.edge_r * risk, edgeOk = c.edge_ci ? c.edge_ci[0] > 0 : null;
      const last = jobs.find((j) => j.setup === s.setup && j.state === "done" && j.report);
      return `<section class="card"><div class="btns" style="justify-content:space-between"><h3>${esc(s.title)}</h3><span class="pill ${cls}">${lab}</span></div>
        <p class="explain">${esc(s.window_ny)} New York · ${esc(why)}${s.trial && s.trial !== "default" ? ` Passed with the retest “${esc(s.trial)}”.` : ""}</p>
        <div class="tiles"><div class="tile"><span class="t">Avg per paper trade</span><b class="${p.avg_usd == null ? "sub" : p.avg_usd >= 0 ? "win" : "loss"}">${usd(p.avg_usd)}</b></div><div class="tile"><span class="t">Paper trades</span><b>${p.trades}</b></div></div>
        ${spark(s.paper_curve)}
        <div class="checks">
          ${chk(c.trades == null ? null : edgeOk, T("Beats random entries", TIPS.random), edgeUsd == null ? "not yet" : `${usd(edgeUsd)}/trade ${edgeUsd >= 0 ? "better" : "worse"}`)}
          ${chk(c.dsr == null ? null : c.dsr > 0.95, T("Not just luck", TIPS.luck), c.dsr == null ? "not yet" : `${pct(c.dsr)} sure`)}
          ${chk(c.trades == null ? null : c.trades >= 100, "Enough trades tested", c.trades == null ? "not yet" : `${c.trades} of 100`)}
          ${chk(c.stress_net_r == null ? null : c.stress_net_r > 0, T("Still profitable with double costs", TIPS.stress), c.stress_net_r == null ? "after the rest pass" : c.stress_net_r > 0 ? "yes" : "no")}
        </div>
        ${(s.reasons || []).length ? `<ul class="explain" style="margin:0;padding-left:18px">${s.reasons.map((r) => `<li>${esc(r)}</li>`).join("")}</ul>` : ""}
        <div class="btns"><button data-backtest="${esc(s.setup)}" ${s.verdict === "retired" ? "disabled" : ""}>Run backtest</button><span class="explain">Re-tests on the full history. Doesn't change live rules.</span></div>
        ${last ? `<p class="explain">Last re-test finished ${nyDay(last.finished_at)}: <code>${esc(last.report)}</code></p>` : ""}
        <details><summary>Advanced numbers</summary><div class="adv">
          <div><span>Paper profit factor <span class="sub">($ won per $1 lost)</span></span><b class="num">${p.profit_factor == null ? "–" : "$" + p.profit_factor.toFixed(2)}</b></div>
          <div><span>Paper Sharpe <span class="sub">(steadiness; above 1 is good)</span></span><b class="num">${p.advanced.sharpe.toFixed(2)}</b></div>
          <div><span>Deflated Sharpe (DSR) <span class="sub">(the "not just luck" score)</span></span><b class="num">${c.dsr == null ? "–" : c.dsr.toFixed(2)}</b></div>
          <div><span>Versions tested <span class="sub">(default + retests)</span></span><b class="num">${s.trials_run} of ${s.rescue_trials + 1}</b></div>
        </div></details></section>`; }).join("")}</div></div>`;
};

VIEWS.models = async () => {
  const m = await api("models"), champ = m.champion;
  const tryout = m.challengers[0];
  return `<div class="stack"><div><h2>Models</h2><p class="lead">The setups find trades; the model decides which ones to take. A model only stays in charge if it does better than taking every setup.</p></div>
    <div class="row">
      <section class="card"><span class="eyebrow">Who's in charge</span>
        <div class="btns">${champ ? `<span class="pill win">Model ${esc(champ.model_id)} is trading</span><span class="pill sub">Rules-only is the backup</span>` : `<span class="pill sub">Rules-only is trading</span>`}</div>
        <p class="explain">${champ ? `In charge since ${nyDay(champ.created_at)}, trained on data up to ${champ.train_end ? nyDay(champ.train_end) : "–"}.` : "No model has passed its tests yet, so every setup that passes the hard risk rules is taken. That's the safe default."}</p>
        ${m.retired.length ? `<p class="explain">Retired: ${m.retired.map((r) => `Model ${esc(r.model_id)}`).join(", ")}.</p>` : ""}</section>
      <section class="card"><span class="eyebrow">In tryout</span>
        ${tryout ? `<h3>Model ${esc(tryout.model_id)}</h3><p class="explain">Runs alongside without trading. It only takes over if it clearly does better.</p>
          <div class="goals"><div class="goal">${ring((tryout.records.disagreements || 0) / 150, "--amber", 64, pct((tryout.records.disagreements || 0) / 150))}<div><span class="t">Trades where they disagree</span><b>${tryout.records.disagreements || 0}</b><span class="explain">need 150</span></div></div>
          <div class="goal">${ring((tryout.records.weeks || 0) / 12, "--amber", 64, `${tryout.records.weeks || 0}/12`)}<div><span class="t">Weeks of tryout</span><b>${tryout.records.weeks || 0}</b><span class="explain">gives up after 12</span></div></div></div>`
          : `<p class="empty">No model in tryout. A new one is trained each weekend once there's enough data.</p>`}
      </section>
    </div></div>`;
};

const FILTERS = [["all", "All"], ["wins", "Wins"], ["losses", "Losses"], ["open", "Open"]];
VIEWS.trades = async (filter = "all") => {
  const list = await api(`trades?filter=${encodeURIComponent(filter)}&limit=200`);
  const max = Math.max(1, ...list.map((t) => Math.abs(t.net_usd || 0)));
  return `<section class="card"><div class="btns" style="justify-content:space-between"><h2>Trades</h2><span class="sub">${list.length} paper trade${list.length === 1 ? "" : "s"}</span></div>
    <div class="filters">${FILTERS.map(([k, l]) => `<button data-filter="${k}" aria-pressed="${k === filter}">${l}</button>`).join("")}</div>
    <div>${list.length ? list.map((t) => tradeRow(t, max)).join("") : `<p class="empty">No trades here yet.</p>`}</div></section>`;
};

VIEWS.trade = async (id) => {
  const t = await api("trades/" + encodeURIComponent(id));
  const won = (t.net_usd || 0) > 0, rr = Math.abs(t.target - t.entry) / Math.abs(t.entry - t.stop);
  const rules = Object.entries(t.rules || {});
  const rv = t.review_fields;
  const head = t.open ? "is still open" : t.exit_reason === "target" ? "hit its target" : t.exit_reason === "stop" ? "was stopped out" : `closed (${esc(t.exit_reason)})`;
  return `<div class="stack"><a class="back" href="#trades">← All trades</a>
    <section class="card"><div class="btns" style="justify-content:space-between"><div><span class="eyebrow">${nyDay(t.entry_time)} · ${nyTime(t.entry_time)} · ${esc(t.setup_title)}</span><h1>${t.side === "long" ? "Long" : "Short"} trade ${head}</h1></div>
      <div style="text-align:right"><b class="num ${won ? "win" : "loss"}" style="font-size:30px">${t.open ? "open" : usd(t.net_usd)}</b><br><span class="sub">${t.r == null ? "" : `${t.r > 0 ? "+" : ""}${t.r.toFixed(2)}`}${T("R", TIPS.R)}</span></div></div>
      ${t.has_chart ? `<img class="chartimg" alt="Chart of the setup window and the trade" src="/api/trades/${encodeURIComponent(t.candidate_id)}/chart">` : `<p class="empty">Entry ${t.entry} · stop ${t.stop} · target ${t.target}${t.exit ? ` · exit ${t.exit}` : ""}. The chart is drawn when the trade closes.</p>`}
    </section>
    <div class="row">
      <section class="card"><span class="eyebrow">Did it follow the rules?</span><div class="checks">
        ${rules.length ? rules.map(([k, ok]) => `<div class="chk"><span class="mark ${ok ? "ok" : "wait"}">${ok ? "✓" : "!"}</span><span>${esc(k.replaceAll("_", " "))}</span><span></span></div>`).join("") : `<p class="explain">No rule checks recorded.</p>`}
      </div><p class="explain">Checked by code, not by Claude.</p></section>
      <section class="card"><span class="eyebrow">${T("Bot confidence", TIPS.conf)}</span>
        ${t.confidence == null ? `<p class="explain">Rules-only was in charge, so no model scored this trade.</p>` : `<div class="vs"><div class="vsbar"><span>This trade</span><span class="track"><i style="width:${t.confidence * 100}%;background:var(--accent)"></i></span><span class="num">${pct(t.confidence)}</span></div>
          <div class="vsbar"><span>Needed to take it</span><span class="track"><i style="width:${(t.confidence_needed || 0) * 100}%;background:var(--sub)"></i></span><span class="num">${pct(t.confidence_needed)}</span></div></div>
          <p class="explain">It aimed to make about ${rr.toFixed(1)}× what it risked. At that payoff, any chance above ${pct(t.confidence_needed)} is worth taking.</p>`}
        <div class="review"><span class="eyebrow">Claude's review</span><b>${esc(bucketWord(t.review))}</b>
          ${rv ? `<span>${esc(rv.summary)}</span>${(rv.reasons || []).length ? `<ul class="explain" style="margin:0;padding-left:18px">${rv.reasons.map((r) => `<li>${esc(r)}</li>`).join("")}</ul>` : ""}` : ""}
          <span class="explain">Claude's opinion only. It never changes the rules or the model.</span></div>
      </section>
    </div></div>`;
};

// A small, safe Markdown renderer for the weekly report: escape first, then format.
function markdown(md) {
  const inline = (s) => esc(s).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>").replace(/`(.+?)`/g, "<code>$1</code>")
    .replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+|#[^)\s]*)\)/g, '<a class="back" href="$2">$1</a>');
  const out = []; let list = null;
  for (const raw of md.split("\n")) {
    const line = raw.trimEnd(), h = line.match(/^(#{1,3}) (.*)/), li = line.match(/^[-*] (.*)/);
    if (!li && list) { out.push(`<ul>${list.join("")}</ul>`); list = null; }
    if (h) out.push(`<h${h[1].length}>${inline(h[2])}</h${h[1].length}>`);
    else if (li) (list ||= []).push(`<li>${inline(li[1])}</li>`);
    else if (line) out.push(`<p>${inline(line)}</p>`);
  }
  if (list) out.push(`<ul>${list.join("")}</ul>`);
  return out.join("");
}

VIEWS.weekly = async (week) => {
  const weeks = await api("weekly");
  if (!weeks.length) return `<section class="card"><h2>Weekly report</h2><p class="empty">The first report is written on a Saturday once there are paper trades.</p></section>`;
  const pick = week || weeks[0].week, text = await api("weekly/" + encodeURIComponent(pick));
  return `<div class="stack"><div class="filters">${weeks.slice(0, 8).map((w) => `<button data-week="${esc(w.week)}" aria-pressed="${w.week === pick}">${esc(w.week)}</button>`).join("")}</div>
    <section class="card"><span class="eyebrow">${esc(pick)} · written Saturday</span><div class="prose">${markdown(text)}</div></section></div>`;
};

const STAGES = ["approve test", "testing", "approve change", "live"];
const STAGE_LABELS = ["Approve test", "Testing", "Approve change", "Live"];
VIEWS.changes = async () => {
  let list;
  try { list = await api("proposals"); } catch (e) {
    return `<section class="card"><h2>Proposed changes</h2><p class="${e.status === 503 ? "empty" : "err"}">${esc(e.message)}</p></section>`;
  }
  const open = list.filter((p) => p.stage !== "closed");
  return `<div class="stack"><div><h2>Proposed changes</h2><p class="lead">Ideas from the weekly report. Each one needs your OK twice: once to test it, and once to use it. Nothing changes without you.</p></div>
    ${open.length ? open.map((p) => { const i = STAGES.indexOf(p.stage);
      return `<section class="card"><div class="steps">${STAGE_LABELS.map((s, k) => `${k ? "<em></em>" : ""}<span class="${k < i ? "done" : k === i ? "on" : ""}">${s}</span>`).join("")}</div>
        <h3>#${p.number} ${esc(p.title)}</h3><p class="explain">${esc(p.body.slice(0, 600))}${p.body.length > 600 ? "…" : ""}</p>
        <div class="btns">${p.needs_you ? `<button class="primary" data-approve="${p.number}">${p.stage === "approve test" ? "Yes, test it" : "Yes, use it"}</button>` : ""}
          ${p.stage !== "live" ? `<button data-reject="${p.number}">No</button>` : ""}<a class="back" href="${esc(p.url)}" target="_blank" rel="noopener">Open on GitHub ↗</a></div></section>`; }).join("")
      : `<section class="card"><p class="empty">No proposals right now.</p></section>`}</div>`;
};

// ---------- routing ----------
const NAV = [["today", "Today"], ["setups", "Setups"], ["models", "Models"], ["trades", "Trades"], ["weekly", "Weekly report"], ["changes", "Changes"]];
let badge = 0;
async function refreshBadge() {
  try { badge = (await api("proposals")).filter((p) => p.needs_you).length; } catch (_) { badge = 0; }
  renderNav();
}
function current() {
  const h = decodeURIComponent(location.hash.slice(1));
  if (h.startsWith("trade/")) return ["trades", () => VIEWS.trade(h.slice(6))];
  const key = VIEWS[h] && h !== "trade" ? h : "today";
  return [key, () => VIEWS[key]()];
}
function renderNav() {
  const [key] = current();
  document.getElementById("nav").innerHTML = NAV.map(([k, l]) => `<a href="#${k}" ${k === key ? 'aria-current="page"' : ""}>${l}${k === "changes" && badge ? `<span class="badge">${badge}</span>` : ""}</a>`).join("");
}
async function show(render) {
  const view = document.getElementById("view");
  try { view.innerHTML = await render(); } catch (e) {
    view.innerHTML = `<section class="card"><p class="err">Couldn't load this page: ${esc(e.message)}</p><p class="explain">Is <code>moon-ai dashboard</code> still running?</p></section>`;
  }
}
async function route() {
  renderNav();
  const [, render] = current();
  await show(render);
  window.scrollTo(0, 0);
}

document.addEventListener("click", async (e) => {
  const b = e.target.closest("button"); if (!b) return;
  try {
    if (b.dataset.filter) await show(() => VIEWS.trades(b.dataset.filter));
    else if (b.dataset.week) await show(() => VIEWS.weekly(b.dataset.week));
    else if (b.dataset.backtest) {
      b.disabled = true;
      await post("backtests", { setup: b.dataset.backtest });
      toast("Backtest queued. It runs in the background; this page shows when it's done.");
      await show(VIEWS.setups);
    } else if (b.dataset.approve || b.dataset.reject) {
      const n = b.dataset.approve || b.dataset.reject, act = b.dataset.approve ? "approve" : "reject";
      if (act === "reject" && !confirm(`Reject proposal #${n}? Its GitHub issue will be closed.`)) return;
      b.disabled = true;
      const r = await post(`proposals/${n}/${act}`);
      toast(`#${n} is now: ${r.stage}.`);
      await Promise.all([show(VIEWS.changes), refreshBadge()]);
    }
  } catch (err) { b.disabled = false; toast(err.message); }
});

const tip = document.getElementById("tip");
function showTip(el) { const r = el.getBoundingClientRect(); tip.textContent = el.dataset.tip; tip.hidden = false; const w = tip.offsetWidth; tip.style.left = Math.max(8, Math.min(innerWidth - w - 8, r.left + r.width / 2 - w / 2)) + "px"; tip.style.top = (r.bottom + 8) + "px"; }
document.addEventListener("mouseover", (e) => { const el = e.target.closest("[data-tip]"); if (el) showTip(el); });
document.addEventListener("mouseout", (e) => { if (e.target.closest("[data-tip]")) tip.hidden = true; });
document.addEventListener("focusin", (e) => { const el = e.target.closest("[data-tip]"); if (el) showTip(el); });
document.addEventListener("focusout", () => { tip.hidden = true; });
document.addEventListener("touchstart", (e) => { const el = e.target.closest("[data-tip]"); if (el) showTip(el); else tip.hidden = true; }, { passive: true });
document.addEventListener("mousemove", (e) => {
  const svg = e.target.closest("#eqsvg"), txt = document.getElementById("hovtxt"); if (!svg || !txt || EQ.length < 2) return;
  const r = svg.getBoundingClientRect(), vx = (e.clientX - r.left) / r.width * 900, i = Math.max(0, Math.min(EQ.length - 1, Math.round((vx - 62) / (900 - 74) * (EQ.length - 1))));
  const p = EQ[i], prev = i ? EQ[i - 1].profit_usd : 0, line = document.getElementById("hov"), X = 62 + i / (EQ.length - 1) * (900 - 74);
  line.setAttribute("x1", X); line.setAttribute("x2", X); line.setAttribute("visibility", "visible");
  txt.innerHTML = `<b>${nyDay(p.t)}</b> · trade ${i + 1}: <b class="${p.profit_usd - prev >= 0 ? "win" : "loss"}">${usd(p.profit_usd - prev)}</b> · ${usd(p.profit_usd)} total${p.dip_usd < 0 ? ` · ${usd(p.dip_usd)} below its high` : " · new high"}`;
});
addEventListener("hashchange", route);
route(); refreshBadge();
