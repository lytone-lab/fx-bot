#!/usr/bin/env python3
import argparse, json, os, sys, webbrowser
import pandas as pd, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import backtest2 as b

HTML = r"""<!doctype html>
<html><head><meta charset="utf-8"><title>JeaFX Dual Replay</title>
<style>
:root{color-scheme:dark} *{box-sizing:border-box}
html,body{margin:0;height:100%;background:#0b0e14;color:#d1d5db;font:13px system-ui;overflow:hidden}
#app{display:flex;height:100vh;width:100vw}
.pane{flex:1;display:flex;flex-direction:column;min-width:0;position:relative;border-right:1px solid #1f2937}
.pane-header{padding:8px;background:#111827;text-align:center;font-weight:bold;color:#f59e0b;border-bottom:1px solid #1f2937;z-index:10}
.canvas-wrap{flex:1;position:relative;overflow:hidden;cursor:crosshair}
canvas{position:absolute;left:0;top:0;display:block;}
#side{width:280px;background:#0f1520;display:flex;flex-direction:column;border-left:1px solid #1f2937;z-index:10}
#ctl{display:flex;gap:8px;padding:8px;background:#111827;border-bottom:1px solid #1f2937}
button{background:#1f2937;color:#e5e7eb;border:1px solid #374151;border-radius:6px;padding:5px 10px;cursor:pointer}
button:hover{background:#374151}
#play{min-width:74px;background:#1d4ed8;border-color:#2563eb}
#scrub{flex:1;margin:0 10px}
label{display:flex;gap:5px;align-items:center;color:#9ca3af}
#side h3{margin:0;padding:10px;font-size:13px;border-bottom:1px solid #1f2937}
#stats{display:grid;grid-template-columns:1fr 1fr;gap:6px;padding:10px;border-bottom:1px solid #1f2937}
#stats div span{display:block;font-size:11px;color:#6b7280}
#stats div b{font-size:14px}
#pos{padding:10px;border-bottom:1px solid #1f2937;min-height:50px}
#list{flex:1;overflow:auto}
.row{padding:6px 10px;border-bottom:1px solid #161e2c;cursor:pointer}
.row:hover{background:#162033}
.g{color:#22c55e}.r{color:#ef4444}.m{color:#9ca3af}.y{color:#f59e0b}
</style></head>
<body>
<div id="app">
 <div class="pane">
  <div class="pane-header">HTF (4h) Trend & Macro Zones</div>
  <div class="canvas-wrap" id="wrap-htf"><canvas id="cv-htf"></canvas></div>
 </div>
 <div class="pane">
  <div class="pane-header">LTF (1h) Trades & Refined Zones</div>
  <div class="canvas-wrap" id="wrap-ltf"><canvas id="cv-ltf"></canvas></div>
 </div>
 <div id="side">
  <div id="ctl">
   <button id="first" title="Reset">&#9198;</button>
   <button id="play">&#9654; Play</button>
   <button id="end" title="End">&#9197;</button>
   <label>Speed <select id="spd"><option>2</option><option>5</option><option selected>10</option><option>20</option></select></label>
   <label style="margin-left:auto"><input type="checkbox" id="pev" checked> Pause</label>
  </div>
  <input type="range" id="scrub" min="0" value="0" style="width:100%;margin:8px 0;padding:0 10px">
  <h3>Replay Stats</h3>
  <div id="stats"></div>
  <div id="pos"></div>
  <div id="list"></div>
 </div>
</div>
<script>
const D = __DATA__;
const B_LTF = D.bars_ltf, B_HTF = D.bars_htf, T = D.trades, E = D.equity, n = B_LTF.length;
const OV_HTF = D.ov_htf, OV_LTF = D.ov_ltf, L2H = D.l2h;
let cur = D.start_at, playing = false, speed = 10;
const dpr = window.devicePixelRatio || 1;
const cvs = {htf: document.getElementById('cv-htf'), ltf: document.getElementById('cv-ltf')};
const ctxs = {htf: cvs.htf.getContext('2d'), ltf: cvs.ltf.getContext('2d')};
const UP='#22c55e', DN='#ef4444';
const fmtP = p => p >= 1000 ? p.toFixed(2) : p.toFixed(4);
const sgn = v => (v >= 0 ? '+' : '') + v.toFixed(2);

let state = {
  htf: { zoomX: 1, zoomY: 1, panX: 0, panY: 0, win: 480 },
  ltf: { zoomX: 1, zoomY: 1, panX: 0, panY: 0, win: 120 }
};

function setupInteractions(k) {
  const el = document.getElementById('wrap-'+k);
  let isDown = false, startX, startY, startPanX, startPanY;
  el.addEventListener('mousedown', e => {
    isDown = true; startX = e.clientX; startY = e.clientY;
    startPanX = state[k].panX; startPanY = state[k].panY;
  });
  window.addEventListener('mouseup', () => isDown = false);
  window.addEventListener('mousemove', e => {
    if (!isDown) return;
    state[k].panX = startPanX + (e.clientX - startX);
    state[k].panY = startPanY + (e.clientY - startY);
    render();
  });
  el.addEventListener('wheel', e => {
    e.preventDefault();
    if (e.shiftKey) {
      state[k].zoomY *= (e.deltaY > 0 ? 1.1 : 0.9);
      state[k].zoomY = Math.max(0.1, Math.min(10, state[k].zoomY));
    } else {
      state[k].zoomX *= (e.deltaY > 0 ? 1.1 : 0.9);
      state[k].zoomX = Math.max(0.1, Math.min(10, state[k].zoomX));
    }
    render();
  }, {passive:false});
}
setupInteractions('htf');
setupInteractions('ltf');

function drawPane(k, bars, cur_idx, trades, zones, isHtf) {
  const cv = cvs[k], ctx = ctxs[k], el = document.getElementById('wrap-'+k);
  cv.width = Math.round(el.clientWidth * dpr); cv.height = Math.round(el.clientHeight * dpr);
  const W = el.clientWidth, H = el.clientHeight;
  ctx.setTransform(dpr,0,0,dpr,0,0); ctx.clearRect(0,0,W,H);
  ctx.font = '11px system-ui';
  
  const padL=10, padR=70, padT=20, padB=20;
  const pH = H - padT - padB;
  const x0 = padL, x1 = W - padR;
  
  const win = state[k].win * state[k].zoomX;
  const bw = (x1-x0)/win;
  const shift = state[k].panX / bw;
  const first = Math.max(0, cur_idx - win + 1) - shift;
  const xOf = i => x0 + (i - first + 0.5) * bw;
  
  let lo=Infinity, hi=-Infinity;
  for (let i=Math.floor(first); i<=cur_idx && i<bars.length; i++) {
    if (i<0 || i>=bars.length) continue;
    lo = Math.min(lo, bars[i][3]); hi = Math.max(hi, bars[i][2]);
  }
  if (lo === Infinity) { lo=0; hi=1; }
  
  const mid = (hi+lo)/2;
  const halfRange = ((hi-lo)/2) / state[k].zoomY;
  const padY = halfRange * 0.1 || 1;
  lo = mid - halfRange - padY + state[k].panY * (halfRange*2/pH);
  hi = mid + halfRange + padY + state[k].panY * (halfRange*2/pH);
  
  const yOf = p => padT + (hi-p)/(hi-lo)*pH;
  
  ctx.strokeStyle='#1f2937'; ctx.fillStyle='#6b7280'; ctx.lineWidth=1; ctx.textAlign='left';
  for (let j=0; j<=4; j++) {
    const p = lo + (hi-lo)*j/4, y = Math.round(yOf(p))+0.5;
    ctx.beginPath(); ctx.moveTo(x0,y); ctx.lineTo(x1,y); ctx.stroke();
    ctx.fillText(fmtP(p), x1+6, y+4);
  }
  
  ctx.save(); ctx.beginPath(); ctx.rect(x0,padT,x1-x0,pH); ctx.clip();
  
  for (const z of zones) {
    if (z.born > cur_idx || z.end < cur_idx - (isHtf ? 8 : 30)) continue;
    const xs = xOf(Math.max(z.born, first)), xe = Math.max(xs+3, xOf(Math.min(z.end, cur_idx+50)));
    const yt = yOf(z.hi), yb = yOf(z.lo), hh = Math.max(1, yb-yt);
    ctx.fillStyle = z.flip ? 'rgba(168,85,247,0.15)' : (z.side>0 ? 'rgba(20,184,166,0.15)' : 'rgba(249,115,22,0.15)');
    ctx.fillRect(xs, yt, xe-xs, hh);
    ctx.strokeStyle = z.flip ? '#a855f7' : (z.side>0 ? '#14b8a6' : '#f97316'); ctx.lineWidth=1;
    ctx.strokeRect(xs+0.5, yt+0.5, xe-xs, hh);
    if (!isHtf) {
        ctx.fillStyle='#e5e7eb'; ctx.textAlign='left'; ctx.fillText((z.side>0?'D':'S'), xs+2, yt-2);
    }
  }
  
  if (!isHtf) {
    for (const t of trades) {
      if (t.entry_i > cur_idx) continue;
      const xs = xOf(t.entry_i), xe = xOf(Math.min(t.exit_i, cur_idx));
      const ye = yOf(t.entry), yt = yOf(t.tp), ys = yOf(t.sl);
      
      ctx.fillStyle = 'rgba(34,197,94,0.1)'; ctx.fillRect(xs, Math.min(ye,yt), xe-xs, Math.abs(yt-ye));
      ctx.fillStyle = 'rgba(239,68,68,0.1)'; ctx.fillRect(xs, Math.min(ye,ys), xe-xs, Math.abs(ys-ye));
      
      ctx.strokeStyle=UP; ctx.beginPath(); ctx.moveTo(xs,yt); ctx.lineTo(xe,yt); ctx.stroke();
      ctx.strokeStyle=DN; ctx.beginPath(); ctx.moveTo(xs,ys); ctx.lineTo(xe,ys); ctx.stroke();
      ctx.strokeStyle='#38bdf8'; ctx.beginPath(); ctx.moveTo(xs,ye); ctx.lineTo(xe,ye); ctx.stroke();
      
      ctx.fillStyle='#38bdf8'; ctx.beginPath(); ctx.arc(xs, ye, 3, 0, 6.3); ctx.fill();
      if (t.add_i >= 0 && t.add_i <= cur_idx) {
        const xa = xOf(t.add_i), ya = yOf(t.add_price), yb = yOf(t.exit_sl);
        ctx.strokeStyle='#facc15'; ctx.setLineDash([4,3]); ctx.beginPath(); ctx.moveTo(xa,yb); ctx.lineTo(Math.max(xa,xe),yb); ctx.stroke(); ctx.setLineDash([]);
        ctx.fillStyle='#facc15'; ctx.beginPath(); ctx.moveTo(xa,ya-5); ctx.lineTo(xa+5,ya); ctx.lineTo(xa,ya+5); ctx.lineTo(xa-5,ya); ctx.closePath(); ctx.fill();
        ctx.fillText('+ add / BE', xa+7, ya-6);
      }
      if (t.exit_i <= cur_idx) {
        ctx.fillStyle = t.pnl > 0 ? UP : DN; ctx.beginPath(); ctx.arc(xe, yOf(t.exit), 3, 0, 6.3); ctx.fill();
      }
    }
  }

  for (let i=Math.floor(first); i<=cur_idx; i++) {
    if (i < 0 || i >= bars.length) continue;
    const [, o,h,l,c] = bars[i], x = xOf(i), up = c>=o;
    ctx.strokeStyle = ctx.fillStyle = up ? UP : DN; ctx.lineWidth=1;
    ctx.beginPath(); ctx.moveTo(Math.round(x)+0.5, yOf(h)); ctx.lineTo(Math.round(x)+0.5, yOf(l)); ctx.stroke();
    const yo = yOf(o), yc = yOf(c);
    const bodyW = Math.max(1, bw*0.7);
    ctx.fillRect(x-bodyW/2, Math.min(yo,yc), bodyW, Math.max(1, Math.abs(yc-yo)));
  }
  ctx.restore();
  
  if (isHtf) {
    ctx.fillStyle='#f59e0b'; ctx.font='bold 14px system-ui'; ctx.textAlign='left';
    let trend = "CONSOLIDATION"; 
    if (cur_idx > 20 && bars[cur_idx][4] > bars[cur_idx-20][4]) trend = "UPTREND";
    else if (cur_idx > 20 && bars[cur_idx][4] < bars[cur_idx-20][4]) trend = "DOWNTREND";
    ctx.fillText("HTF TREND: " + trend, x0+10, padT+20);
  }
}

function render() {
  const cur_htf = L2H[cur];
  drawPane('htf', B_HTF, cur_htf, T, OV_HTF.zones, true);
  drawPane('ltf', B_LTF, cur, T, OV_LTF.zones, false);
  
  let closed=0, wins=0, pnl=0;
  for (const t of T) if (t.exit_i <= cur) { closed++; pnl+=t.pnl; if(t.pnl>0) wins++; }
  const eq = E[cur], ret = (eq/D.meta.capital - 1)*100;
  document.getElementById('stats').innerHTML =
    `<div><span>Equity</span><b class="${ret>=0?'g':'r'}">${eq.toFixed(2)}</b></div>` +
    `<div><span>Return</span><b class="${ret>=0?'g':'r'}">${sgn(ret)}%</b></div>` +
    `<div><span>Trades</span><b>${closed}</b></div>` +
    `<div><span>Win%</span><b>${closed?(wins/closed*100).toFixed(0):0}%</b></div>`;
  
  const open = T.find(t => t.entry_i <= cur && t.exit_i > cur);
  if (open) {
    const added = open.add_i >= 0 && open.add_i <= cur;
    document.getElementById('pos').innerHTML = `<b class="${open.side==='LONG'?'g':'r'}">${open.side} open</b><br>Entry ${fmtP(open.entry)} SL ${fmtP(open.sl)} TP ${fmtP(open.tp)}` +
      (added ? `<br><span class="y">Pyramided @ ${fmtP(open.add_price)}, avg ${fmtP(open.avg_entry)}, SL -> BE ${fmtP(open.exit_sl)}</span>` : '');
  } else {
    document.getElementById('pos').innerHTML = '<span class="m">No open position</span>';
  }
  document.getElementById('scrub').value = cur;
  document.getElementById('play').innerHTML = playing ? '&#10074;&#10074; Pause' : '&#9654; Play';
}

document.getElementById('play').onclick = () => { playing = !playing; render(); };
document.getElementById('first').onclick = () => { cur = 0; playing = false; render(); };
document.getElementById('end').onclick = () => { cur = n - 1; playing = false; render(); };
document.getElementById('scrub').oninput = e => { cur = +e.target.value; playing = false; render(); };
window.addEventListener('resize', () => render());

let last = performance.now(), acc = 0;
const evBars = new Set(); T.forEach(t => { evBars.add(t.entry_i); evBars.add(t.exit_i); });
function loop(now) {
  const dt = Math.min(0.25, (now-last)/1000); last = now;
  if (playing) {
    acc += dt * speed;
    while (acc >= 1) {
      acc -= 1;
      if (cur < n-1) {
        cur++;
        if (document.getElementById('pev').checked && evBars.has(cur)) { playing = false; acc = 0; break; }
      } else { playing = false; acc = 0; break; }
    }
    render();
  }
  requestAnimationFrame(loop);
}
render(); requestAnimationFrame(loop);
</script></body></html>
"""

def build(df_ltf, df_htf, trades, curve, meta, start_at, overlays_ltf, overlays_htf, l2h):
    idx = df_ltf.index
    ms = ((idx - pd.Timestamp("1970-01-01", tz="UTC")) // pd.Timedelta("1ms")).astype("int64")
    bars_ltf = [[int(t), float(o), float(h), float(l), float(c)] for t,o,h,l,c in zip(ms, df_ltf["open"], df_ltf["high"], df_ltf["low"], df_ltf["close"])]
    
    idx_h = df_htf.index
    ms_h = ((idx_h - pd.Timestamp("1970-01-01", tz="UTC")) // pd.Timedelta("1ms")).astype("int64")
    bars_htf = [[int(t), float(o), float(h), float(l), float(c)] for t,o,h,l,c in zip(ms_h, df_htf["open"], df_htf["high"], df_htf["low"], df_htf["close"])]

    tl = []
    if len(trades):
        ei = idx.get_indexer(trades["entry_time"])
        xi = idx.get_indexer(trades["exit_time"])
        ai = idx.get_indexer(pd.DatetimeIndex(trades["add_time"])) if "add_time" in trades else np.full(len(trades), -1)
        for r, a, z, ad in zip(trades.itertuples(), ei, xi, ai):
            tl.append({"id": int(r.id), "side": r.side, "entry_i": int(a), "exit_i": int(z), "entry": float(r.entry),
                       "sl": float(r.sl), "tp": float(r.tp), "exit": float(r.exit), "reason": r.reason,
                       "pnl": float(r.pnl), "r": float(r.r), "qty": float(r.qty), "add_i": int(ad),
                       "add_price": float(getattr(r, "add_price", 0) or 0) if ad >= 0 else 0.0,
                       "avg_entry": float(getattr(r, "avg_entry", r.entry)), "exit_sl": float(getattr(r, "exit_sl", r.sl))})

    data = {
        "bars_ltf": bars_ltf, "bars_htf": bars_htf, "trades": tl, "equity": [float(v) for v in curve.values],
        "start_at": int(start_at), "meta": meta,
        "ov_ltf": overlays_ltf, "ov_htf": overlays_htf, "l2h": [int(v) for v in l2h]
    }
    return HTML.replace("__DATA__", json.dumps(data))

def main():
    p = argparse.ArgumentParser()
    p.add_argument("path", nargs="?")
    p.add_argument("--tf", default="4h")
    p.add_argument("--strategy", choices=b.STRATEGIES, default="trend_atr")
    p.add_argument("--params", default="")
    p.add_argument("--market", choices=["spot", "futures"], default="spot")
    p.add_argument("--start")
    p.add_argument("--end")
    p.add_argument("--bars", type=int, default=1500)
    p.add_argument("--capital", type=float, default=1000.0)
    p.add_argument("--risk", type=float, default=0.01)
    p.add_argument("--leverage", type=float, default=1.0)
    p.add_argument("--fee", type=float)
    p.add_argument("--slip", type=float)
    p.add_argument("--funding", type=float)
    p.add_argument("--out", default="out/replay.html")
    p.add_argument("--no-open", action="store_true")
    p.add_argument("--synthetic", action="store_true")
    a = p.parse_args()

    futures = a.market == "futures"
    fee = a.fee if a.fee is not None else (0.0005 if futures else 0.001)
    slip = a.slip if a.slip is not None else (0.0003 if futures else 0.0005)
    funding = a.funding if a.funding is not None else (0.0001 if futures else 0.0)
    leverage = a.leverage if futures else 1.0

    df = b.synthetic() if a.synthetic else b.load(a.path)
    full_index = df.index
    params = b.parse_params(a.params)
    sig = b.STRATEGIES[a.strategy](df, **params)
    if a.start:
        m = df.index >= pd.Timestamp(a.start, tz="UTC")
        df, sig = df[m], sig[m]
    if a.end:
        m = df.index <= pd.Timestamp(a.end, tz="UTC")
        df, sig = df[m], sig[m]
    df, sig = df.iloc[-a.bars:], sig.iloc[-a.bars:]

    trades, curve = b.run_engine(df, sig, fee, slip, a.risk, leverage, a.capital, futures, funding, a.tf)
    first_entry = df.index.get_loc(trades["entry_time"].iloc[0]) if len(trades) else 0
    start_at = max(0, first_entry - 60)
    
    sym = os.path.basename(a.path).replace(".csv", "") if a.path else "synthetic"
    meta = {"title": f"{sym} | {a.strategy} | {a.market}", "capital": a.capital, "tf": a.tf, "intraday": a.tf != "1d"}
    
    rule = {'1h': '4h', '15m': '1h', '4h': '1d', '1d': '1W'}.get(a.tf, '4h')
    df_htf = df.resample(rule, closed='left', label='left').agg({'open':'first','high':'max','low':'min','close':'last','volume':'sum'}).dropna()
    l2h = np.clip(df_htf.index.searchsorted(df.index, side="right") - 1, 0, max(0, len(df_htf) - 1))

    ov_ltf = {"zones": [], "bos": [], "swings": []}
    ov_htf = {"zones": [], "bos": [], "swings": []}
    if a.strategy == "jeafx":
        import jeafx
        ov = jeafx.LAST_OVERLAYS
        off, last = full_index.get_loc(df.index[0]), len(df) - 1
        
        def map_ov(ov_data, off):
            return {
                "zones": [{"side": z["side"], "lo": z["lo"], "hi": z["hi"], "flip": z["flip"], "born": z["born"]-off, "end": z["end"]-off} for z in ov_data["zones"] if z["end"]-off >= 0 and z["born"]-off <= last],
                "bos": [{"dir": d_, "level": lv, "from": fr-off, "i": bi-off} for d_, lv, fr, bi in ov_data["bos"] if bi-off >= 0 and bi-off <= last],
                "swings": [{"kind": kd, "price": pr, "idx": ix-off, "conf": cf-off} for kd, pr, ix, cf in ov_data["swings"] if cf-off >= 0 and ix-off <= last]
            }
        ov_ltf = map_ov(ov, off)
        to_h = lambda j: int(l2h[min(max(j, 0), last)])  # LTF bar -> HTF bar index for the left pane
        ov_htf = {"zones": [{"side": z["side"], "lo": z.get("htf_lo", z["lo"]), "hi": z.get("htf_hi", z["hi"]), "flip": z["flip"],
                             "born": to_h(z["born"]), "end": to_h(z["end"])} for z in ov_ltf["zones"]],
                  "bos": [], "swings": []}

    html = build(df, df_htf, trades, curve, meta, start_at, ov_ltf, ov_htf, l2h)
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f: f.write(html)
    print(f"replay saved -> {a.out}  ({len(df)} candles, {len(trades)} trades)")
    if not a.no_open: webbrowser.open("file://" + os.path.abspath(a.out))

if __name__ == "__main__":
    main()
