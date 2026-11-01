"""The ground-truth review page: one self-contained HTML file to mark days on.

Built from the ground-truth prototype (#11) and the dashboard's plain-language
rules (#12). Each sampled day shows the setup's window as a candle chart with
the bot's detections drawn on it. You mark each detection agree, disagree or
unsure, click a candle to add a setup it missed, then export a JSON file.
`moon-ai review-days --import <file>` turns that file into the CI fixture.
"""

from __future__ import annotations

import html
import json
from datetime import date, datetime, timedelta

from moon_ai.config import load_config
from moon_ai.data.store import BarStore
from moon_ai.groundtruth import detect, export_template, key
from moon_ai.sessions import NY, to_ny
from moon_ai.setups import load_setup_defaults


def build(setup: str, days: list[date], store: BarStore) -> str:
    cfg = load_config()
    d = load_setup_defaults()[setup]
    win = cfg.sessions.windows[d.params.window]
    data, found_by_day = [], {}
    for day in days:
        found, bars = detect(setup, store, day, cfg)
        lo = datetime.combine(day, win.start, tzinfo=NY) - timedelta(hours=2)
        hi = datetime.combine(day, win.end, tzinfo=NY) + timedelta(hours=1)
        shown = [b for b in bars if lo <= to_ny(b.ts_open) < hi]
        found_by_day[day.isoformat()] = found
        data.append(
            {
                "day": day.isoformat(),
                "bars": [
                    [to_ny(b.ts_open).strftime("%H:%M"), b.open, b.high, b.low, b.close]
                    for b in shown
                ],
                "window": [win.start.strftime("%H:%M"), win.end.strftime("%H:%M")],
                "found": [
                    {
                        "key": key(c),
                        "side": c.side,
                        "t": to_ny(c.decision_time).strftime("%H:%M"),
                        "entry": c.entry,
                        "stop": c.stop,
                        "target": c.target,
                        "why": c.rule_results,
                    }
                    for c in found
                ],
            }
        )
    template = export_template(setup, found_by_day)
    return (
        PAGE.replace("/*TITLE*/", html.escape(d.title))
        .replace("/*DATA*/null", json.dumps(data))
        .replace("/*TEMPLATE*/null", json.dumps(template))
    )


PAGE = r"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>/*TITLE*/ ground-truth review</title>
<style>
:root{--bg:#f3f4f8;--card:#fff;--ink:#161a2b;--sub:#5d6378;--line:#e1e4ee;--win:#12a37f;--loss:#e0533f;
--amber:#d99417;--accent:#4b5bd6;--soft:rgba(75,91,214,.1)}
@media (prefers-color-scheme:dark){:root{--bg:#0c0f1d;--card:#151a2e;--ink:#e9ebf5;--sub:#9aa1bd;
--line:#262c47;--win:#35d0a5;--loss:#ff7a66;--amber:#f0b440;--accent:#8d9bff;--soft:rgba(141,155,255,.13)}}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 system-ui,-apple-system,sans-serif}
main{max-width:1100px;margin:0 auto;padding:20px 16px 60px;display:grid;gap:16px}
h1{margin:0;font-size:26px}.sub{color:var(--sub);font-size:13px}
.card{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:16px 18px;display:grid;gap:10px}
.top{display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap;align-items:center}
.scroll{overflow-x:auto}svg text{font-size:10px;fill:var(--sub)}
.det{display:grid;grid-template-columns:1fr auto;gap:8px;align-items:center;padding:8px 10px;border-radius:10px;background:var(--bg)}
.det b{font-size:14px}.btns{display:flex;gap:6px;flex-wrap:wrap}
button{font:600 13px system-ui;border:1px solid var(--line);background:var(--card);color:var(--ink);padding:6px 12px;border-radius:999px;cursor:pointer}
button[aria-pressed=true][data-v=agree]{background:var(--win);color:#fff;border-color:var(--win)}
button[aria-pressed=true][data-v=disagree]{background:var(--loss);color:#fff;border-color:var(--loss)}
button[aria-pressed=true][data-v=unsure]{background:var(--amber);color:#fff;border-color:var(--amber)}
button.primary{background:var(--accent);color:#fff;border-color:var(--accent)}
.bar{position:sticky;bottom:0;background:var(--card);border-top:1px solid var(--line);padding:10px 16px;
display:flex;gap:12px;justify-content:space-between;align-items:center;flex-wrap:wrap}
</style></head><body><main>
<div><h1>/*TITLE*/: does the bot see what you see?</h1>
<p class="sub">For each day: mark every setup the bot found as <b>agree</b>, <b>disagree</b> or <b>unsure</b>.
If you see a setup it missed, click the candle where it would have entered. Then export and send the file.
Shaded area = the setup's window. Green line = entry, red = stop, blue = target.</p></div>
<div id="days"></div></main>
<div class="bar"><span id="progress" class="sub"></span>
<span class="btns"><button class="primary" id="export">Export my verdicts</button></span></div>
<script>
const DATA=/*DATA*/null, OUT=/*TEMPLATE*/null;
const cssv=n=>getComputedStyle(document.documentElement).getPropertyValue(n).trim();
function chart(d){
  const B=d.bars,W=Math.max(700,B.length*5+60),H=300,top=10,bot=22;if(!B.length)return'<p class=sub>No bars.</p>';
  let lo=Math.min(...B.map(b=>b[3])),hi=Math.max(...B.map(b=>b[2]));
  d.found.forEach(f=>{[f.entry,f.stop,f.target].forEach(p=>{if(p!=null){lo=Math.min(lo,p);hi=Math.max(hi,p)}})});
  const pad=(hi-lo)*.05;lo-=pad;hi+=pad;const y=p=>top+(hi-p)/(hi-lo)*(H-top-bot),idx={};B.forEach((b,i)=>idx[b[0]]=i);
  const x=t=>(idx[t]??0)*5+3;let s='';
  const w0=idx[d.window[0]],w1=idx[d.window[1]]??B.length;
  if(w0!=null)s+=`<rect x="${w0*5}" y="${top}" width="${(w1-w0)*5}" height="${H-top-bot}" fill="${cssv('--soft')}"/>`;
  B.forEach((b,i)=>{if(b[0].endsWith(':00')||b[0].endsWith(':30'))s+=`<text x="${i*5}" y="${H-6}">${b[0]}</text>`});
  d.found.forEach((f,n)=>{const X=x(f.t);[[f.entry,'--win'],[f.stop,'--loss'],[f.target,'--accent']].forEach(([p,c])=>{
    if(p!=null)s+=`<line x1="${X}" x2="${Math.min(W,X+150)}" y1="${y(p)}" y2="${y(p)}" stroke="${cssv(c)}" stroke-width="1.5"/>`});
    s+=`<text x="${X+2}" y="${y(f.entry)-4}" style="fill:${cssv('--ink')};font-weight:700">#${n+1}</text>`});
  B.forEach((b,i)=>{const c=cssv(b[4]>=b[1]?'--win':'--loss'),X=i*5+1;
    s+=`<g data-day="${d.day}" data-t="${b[0]}" style="cursor:crosshair"><rect x="${X-1}" y="${top}" width="5" height="${H-top-bot}" fill="transparent"/>`+
       `<line x1="${X+1.5}" x2="${X+1.5}" y1="${y(b[2])}" y2="${y(b[3])}" stroke="${c}"/>`+
       `<rect x="${X}" y="${y(Math.max(b[1],b[4]))}" width="3" height="${Math.max(1,Math.abs(y(b[1])-y(b[4])))}" fill="${c}"/></g>`});
  (OUT.days[d.day].missed||[]).forEach(m=>{const t=m.t.slice(11,16);if(idx[t]!=null)s+=`<text x="${x(t)-3}" y="${top+10}" style="fill:${cssv('--accent')};font-size:14px">▼</text>`});
  return `<div class=scroll><svg viewBox="0 0 ${W} ${H}" width="${W}" height="${H}">${s}</svg></div>`;
}
function render(){
  document.getElementById('days').innerHTML=DATA.map((d,i)=>{const o=OUT.days[d.day];
    const dets=d.found.map((f,n)=>{const v=o.verdicts[f.key]||'';const why=Object.entries(f.why).map(([k,x])=>`${k.replace(/_/g,' ')}: ${Array.isArray(x)?x.join('–'):x}`).join(' · ');
      return `<div class=det><div><b>#${n+1} ${f.side} at ${f.t}</b> <span class=sub>entry ${f.entry} · stop ${f.stop} · target ${f.target}</span><br><span class=sub>${why}</span></div>
      <div class=btns>${['agree','disagree','unsure'].map(k=>`<button data-key="${f.key}" data-day="${d.day}" data-v="${k}" aria-pressed="${v===k}">${k}</button>`).join('')}</div></div>`}).join('');
    const missed=(o.missed||[]).map((m,k)=>`<div class=det><div><b>You added: ${m.side} at ${m.t.slice(11,16)}</b></div><div class=btns>
      <button data-flip="${d.day}|${k}">${m.side==='long'?'make it short':'make it long'}</button><button data-del="${d.day}|${k}">remove</button></div></div>`).join('');
    return `<section class=card><div class=top><b>Day ${i+1} of ${DATA.length}: ${d.day}</b><span class=sub>${d.found.length} found by the bot</span></div>
      ${chart(d)}${dets||'<p class=sub>The bot found nothing this day. Click a candle if you see a setup.</p>'}${missed}</section>`}).join('');
  const total=DATA.reduce((n,d)=>n+d.found.length,0),done=DATA.reduce((n,d)=>n+Object.values(OUT.days[d.day].verdicts).filter(Boolean).length,0);
  document.getElementById('progress').textContent=`${done} of ${total} detections marked · ${DATA.reduce((n,d)=>n+OUT.days[d.day].missed.length,0)} missed setups added`;
}
document.addEventListener('click',e=>{const b=e.target.closest('button[data-v]');
  if(b){const v=OUT.days[b.dataset.day].verdicts;v[b.dataset.key]=v[b.dataset.key]===b.dataset.v?'':b.dataset.v;return render()}
  const del=e.target.closest('[data-del]');if(del){const[d,k]=del.dataset.del.split('|');OUT.days[d].missed.splice(+k,1);return render()}
  const flip=e.target.closest('[data-flip]');if(flip){const[d,k]=flip.dataset.flip.split('|');const m=OUT.days[d].missed[+k];m.side=m.side==='long'?'short':'long';return render()}
  const g=e.target.closest('g[data-t]');if(g){OUT.days[g.dataset.day].missed.push({t:`${g.dataset.day}T${g.dataset.t}`,side:'long'});render()}});
document.getElementById('export').onclick=()=>{const blob=new Blob([JSON.stringify(OUT,null,1)],{type:'application/json'});
  const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download=`ground-truth-${OUT.setup}.json`;a.click()};
render();
</script></body></html>"""
