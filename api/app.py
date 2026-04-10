from __future__ import annotations

import importlib
import os
import sys
import traceback

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

_hwl = importlib.import_module("h1b_weighted_lottery")
GroupResult = _hwl.GroupResult
estimate_h1b = _hwl.estimate_h1b
estimate_h1b_unweighted = _hwl.estimate_h1b_unweighted

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>H-1B Lottery Probability Estimator</title>
  <style>
    :root { font-family: system-ui, sans-serif; line-height: 1.5; max-width: 44rem; margin: 2rem auto; padding: 0 1.25rem; color: #1c1c1e; }
    h1 { font-size: 1.5rem; margin-bottom: 0.25rem; }
    h2 { font-size: 1.1rem; margin-top: 2rem; }
    p.sub { color: #636366; font-size: 0.9rem; margin-top: 0; }
    code { background: #f2f2f7; padding: 0.1em 0.4em; border-radius: 4px; font-size: 0.88em; }
    pre { background: #f2f2f7; padding: 1rem; border-radius: 8px; overflow: auto; font-size: 0.88em; }
    fieldset { border: 1px solid #d1d1d6; border-radius: 8px; padding: 1rem 1.25rem; margin-bottom: 1rem; }
    legend { font-weight: 600; padding: 0 0.4rem; font-size: 0.95rem; }
    .row { display: flex; gap: 1rem; flex-wrap: wrap; margin-top: 0.5rem; }
    .field { display: flex; flex-direction: column; gap: 0.25rem; }
    label { font-size: 0.85rem; color: #48484a; }
    input[type=number], input[type=text], select { padding: 0.35rem 0.5rem; border: 1px solid #c7c7cc; border-radius: 6px; font-size: 0.95rem; width: 9rem; }
    select { width: auto; }
    button { margin-top: 1rem; padding: 0.55rem 1.4rem; background: #007aff; color: #fff; border: none; border-radius: 8px; font-size: 1rem; cursor: pointer; }
    button:hover { background: #005ecb; }
    table { border-collapse: collapse; width: 100%; font-size: 0.9rem; }
    th { text-align: left; padding: 0.4rem 0.6rem; background: #f2f2f7; font-weight: 600; }
    td { padding: 0.4rem 0.6rem; border-top: 1px solid #e5e5ea; }
    .tag { display: inline-block; padding: 0.15em 0.5em; border-radius: 4px; font-size: 0.8em; font-weight: 600; }
    .tag-nm { background: #e8f4fd; color: #0a7ab5; }
    .tag-m  { background: #fef0e6; color: #c04a00; }
    .overall { margin-top: 0.75rem; font-size: 1rem; font-weight: 600; }
    .err { color: #c0392b; }
  </style>
</head>
<body>
  <h1>H-1B Lottery Probability Estimator</h1>
  <p class="sub">Educational model only — not legal or immigration advice.</p>

  <fieldset>
    <legend>Population</legend>
    <div class="row">
      <div class="field"><label>Total registrations N</label><input type="number" id="N" value="336153" min="1" /></div>
      <div class="field"><label>Master&#39;s-eligible share m (0–1)</label><input type="number" id="m" value="0.3557" step="0.0001" min="0" max="1" /></div>
    </div>
  </fieldset>

  <fieldset>
    <legend>Non-master&#39;s wage distribution (%)</legend>
    <div class="row">
      <div class="field"><label>Level 1</label><input type="number" id="r1" value="20" min="0" /></div>
      <div class="field"><label>Level 2</label><input type="number" id="r2" value="61" min="0" /></div>
      <div class="field"><label>Level 3</label><input type="number" id="r3" value="13" min="0" /></div>
      <div class="field"><label>Level 4</label><input type="number" id="r4" value="6"  min="0" /></div>
    </div>
  </fieldset>

  <fieldset>
    <legend>Master&#39;s-eligible wage distribution (%)</legend>
    <div class="row">
      <div class="field"><label>Level 1</label><input type="number" id="s1" value="35" min="0" /></div>
      <div class="field"><label>Level 2</label><input type="number" id="s2" value="50" min="0" /></div>
      <div class="field"><label>Level 3</label><input type="number" id="s3" value="11" min="0" /></div>
      <div class="field"><label>Level 4</label><input type="number" id="s4" value="4"  min="0" /></div>
    </div>
  </fieldset>

  <div class="field" style="margin-bottom:0.5rem">
    <label>Mode</label>
    <select id="mode">
      <option value="weighted">Wage-weighted (Level 1–4 weights 1/2/3/4)</option>
      <option value="unweighted">Unweighted two-pool (legacy)</option>
    </select>
  </div>

  <button type="button" id="go">Compute</button>

  <div id="result" style="margin-top:1.5rem"></div>

  <script>
  document.getElementById("go").onclick = async () => {
    const v = (id) => Number(document.getElementById(id).value);
    const payload = {
      N: v("N"), m: v("m"),
      r: [v("r1"), v("r2"), v("r3"), v("r4")],
      s: [v("s1"), v("s2"), v("s3"), v("s4")],
      mode: document.getElementById("mode").value,
    };
    document.getElementById("result").innerHTML = "<p>Computing…</p>";
    try {
      const resp = await fetch("/compute", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await resp.json();
      if (!data.ok) {
        document.getElementById("result").innerHTML =
          "<p class='err'>Error: " + data.error + "</p>";
        return;
      }
      const r = data.result;
      const pct = (x) => (x * 100).toFixed(2) + "%";
      let rows = "";
      for (const [lv, g] of Object.entries(r.non_results)) {
        rows += "<tr><td><span class='tag tag-nm'>Non-master&#39;s</span></td>" +
          "<td>" + lv + "</td><td>" + g.count.toLocaleString() + "</td>" +
          "<td>" + pct(g.regular_prob) + "</td><td>N/A</td>" +
          "<td><strong>" + pct(g.final_prob) + "</strong></td></tr>";
      }
      for (const [lv, g] of Object.entries(r.master_results)) {
        rows += "<tr><td><span class='tag tag-m'>Master&#39;s</span></td>" +
          "<td>" + lv + "</td><td>" + g.count.toLocaleString() + "</td>" +
          "<td>" + pct(g.regular_prob) + "</td>" +
          "<td>" + (g.master_cap_cond !== null ? pct(g.master_cap_cond) : "N/A") + "</td>" +
          "<td><strong>" + pct(g.final_prob) + "</strong></td></tr>";
      }
      document.getElementById("result").innerHTML =
        "<h2>Results</h2>" +
        "<table><thead><tr><th>Category</th><th>Wage level</th><th>Count</th>" +
        "<th>Round 1</th><th>Round 2 (cond.)</th><th>Final P</th></tr></thead>" +
        "<tbody>" + rows + "</tbody></table>" +
        "<p class='overall'>Overall selection probability: " + pct(r.overall_prob) + "</p>" +
        "<p class='sub'>Regular cap slots: " + Math.round(r.regular_draws).toLocaleString() +
        " &nbsp;|&nbsp; Master&#39;s cap effective slots: " + Math.round(r.master_draws).toLocaleString() + "</p>";
    } catch (e) {
      document.getElementById("result").innerHTML = "<p class='err'>" + e + "</p>";
    }
  };
  </script>
</body>
</html>"""


def _serialize(res: dict) -> dict:
    def one(g: GroupResult) -> dict:
        return {
            "count": g.count,
            "regular_prob": g.regular_prob,
            "final_prob": g.final_prob,
            "master_cap_cond": g.master_cap_cond,
        }

    return {
        "N": res["N"],
        "m": res["m"],
        "overall_prob": res["overall_prob"],
        "regular_draws": res["regular_draws"],
        "master_draws": res["master_draws"],
        "non_results": {k: one(v) for k, v in res["non_results"].items()},
        "master_results": {k: one(v) for k, v in res["master_results"].items()},
    }


@app.get("/", response_class=HTMLResponse)
async def homepage():
    return HTMLResponse(content=_HTML)


@app.post("/compute")
async def post_compute(request: Request):
    try:
        data = await request.json()
        N = int(data["N"])
        m = float(data["m"])
        r = [float(x) for x in data["r"]]
        s = [float(x) for x in data["s"]]
        mode = str(data.get("mode", "weighted")).lower()
        if len(r) != 4 or len(s) != 4:
            return JSONResponse(
                status_code=400,
                content={"ok": False, "error": "r and s must have 4 values each"},
            )
        if mode == "unweighted":
            res = estimate_h1b_unweighted(N, m, r, s)
        else:
            res = estimate_h1b(N, m, r, s)
        return {"ok": True, "result": _serialize(res)}
    except (KeyError, TypeError, ValueError) as e:
        return JSONResponse(status_code=400, content={"ok": False, "error": str(e)})
    except Exception:
        return JSONResponse(
            status_code=500, content={"ok": False, "error": traceback.format_exc()}
        )
