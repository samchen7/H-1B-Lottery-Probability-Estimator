# H-1B Lottery Probability Estimator

A single-file Python tool to estimate **H-1B cap selection probabilities** under two stylized lottery models. Runs locally as a CLI or Gradio dashboard, and deploys to Vercel as a web app.

> Not legal, immigration, or tax advice. For educational and rough estimation purposes only.

---

## Models

| Mode | Description |
|------|-------------|
| **Wage-weighted** | Level 1–4 weights 1/2/3/4. Each round uses an exponential-tilt approximation so that expected selections match the cap. |
| **Unweighted two-pool** | Uniform random selection in round 1; uniform among remaining master's-eligible in round 2. |

Both modes use:

- **Round 1 — Regular cap:** up to **65,000** selections from all registrations.
- **Round 2 — Master's cap:** up to **20,000** additional selections from master's-eligible who did not win round 1.

Results show per–wage-level selection probabilities for non-master's and master's-eligible applicants, plus the conditional round-2 probability for master's-eligible.

---

## Inputs

| Parameter | Meaning |
|-----------|---------|
| `N` | Total registrations |
| `m` | Master's-eligible share (0–1) |
| `r1..r4` | Non-master's wage level distribution (any positive scale; auto-normalized) |
| `s1..s4` | Master's-eligible wage level distribution (auto-normalized) |

---

## Run locally

### CLI

```bash
python3 h1b_weighted_lottery.py \
  --N 336153 --m 0.3557 \
  --r 0.20 0.61 0.13 0.06 \
  --s 0.35 0.50 0.11 0.04
```

Add `--unweighted` for the legacy two-pool model. Omit flags to enter interactive mode.

### Gradio dashboard

```bash
pip install gradio pandas
python3 h1b_weighted_lottery.py --dashboard
```

Opens at `http://127.0.0.1:7860`.

---

## Deploy on Vercel

1. Push to GitHub.
2. Import the repository at [vercel.com/new](https://vercel.com/new) (framework preset: **Other**).
3. Deploy — Vercel detects `requirements.txt` (FastAPI) and `api/app.py` as the ASGI entrypoint.

After deploy:

| Path | Purpose |
|------|---------|
| `/` | Web calculator (HTML + JS, served by FastAPI) |
| `POST /compute` | JSON computation API |

**POST `/compute` body:**

```json
{
  "N": 336153,
  "m": 0.3557,
  "r": [0.20, 0.61, 0.13, 0.06],
  "s": [0.35, 0.50, 0.11, 0.04],
  "mode": "weighted"
}
```

`mode`: `"weighted"` (default) or `"unweighted"`.

---

## Files

| File | Role |
|------|------|
| `h1b_weighted_lottery.py` | Core estimator, CLI, optional Gradio UI |
| `api/app.py` | FastAPI app: serves web UI at `/` and JSON API at `/compute` |
| `requirements.txt` | `fastapi` for the Vercel deployment |
| `README.md` | This file |

---

## Limitations

- Ignores exemptions, country caps, multiple registrations, and post-selection steps.
- Weighted mode is a mathematical approximation, not a certified USCIS algorithm replica.
- Outputs are expectations under the model, not guarantees.
