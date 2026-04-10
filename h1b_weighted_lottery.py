from __future__ import annotations

import argparse
import math
from dataclasses import dataclass
from typing import Dict, List, Sequence, Tuple


REGULAR_CAP = 65000
MASTER_CAP = 20000
LEVELS = [1, 2, 3, 4]
WEIGHTS = [1.0, 2.0, 3.0, 4.0]

SHOW_MODE_FULL = "With Regular / Master breakdown"
SHOW_MODE_SIMPLE = "Final probability only"


@dataclass
class GroupResult:
    count: int
    regular_prob: float
    final_prob: float
    master_cap_cond: float | None = None


def normalize_dist(dist: Sequence[float]) -> List[float]:
    if len(dist) != 4:
        raise ValueError("Distribution must have exactly 4 values (Level 1–4).")
    if any(x < 0 for x in dist):
        raise ValueError("Distribution values cannot be negative.")
    s = sum(dist)
    if s <= 0:
        raise ValueError("Distribution must sum to a positive number.")
    return [x / s for x in dist]


def allocate_counts(total: int, ratios: Sequence[float]) -> List[int]:
    ratios = normalize_dist(ratios)
    raw = [total * r for r in ratios]
    base = [int(math.floor(x)) for x in raw]
    remain = total - sum(base)
    order = sorted(range(4), key=lambda i: raw[i] - base[i], reverse=True)
    for i in order[:remain]:
        base[i] += 1
    return base


def solve_lambda(
    counts: Sequence[float],
    weights: Sequence[float],
    target_draws: float,
    tol: float = 1e-12,
    max_iter: int = 200,
) -> float:
    total = float(sum(counts))
    if target_draws <= 0:
        return 0.0
    if target_draws >= total:
        return 1e9

    def f(lam: float) -> float:
        return sum(c * (1.0 - math.exp(-lam * w)) for c, w in zip(counts, weights))

    lo, hi = 0.0, 1.0
    while f(hi) < target_draws:
        hi *= 2.0
        if hi > 1e9:
            break

    for _ in range(max_iter):
        mid = (lo + hi) / 2.0
        val = f(mid)
        if abs(val - target_draws) <= tol:
            return mid
        if val < target_draws:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


def draw_probs_by_group(
    counts: Sequence[float],
    weights: Sequence[float],
    draws: float,
) -> List[float]:
    total = float(sum(counts))
    if total <= 0:
        return [0.0 for _ in counts]
    draws = max(0.0, min(draws, total))
    if draws <= 0:
        return [0.0 for _ in counts]
    if draws >= total:
        return [1.0 for _ in counts]

    lam = solve_lambda(counts, weights, draws)
    return [1.0 - math.exp(-lam * w) for w in weights]


def estimate_h1b(
    N: int,
    m: float,
    r: Sequence[float],
    s: Sequence[float],
) -> Dict[str, object]:
    if N <= 0:
        raise ValueError("N must be a positive integer.")
    if not (0.0 <= m <= 1.0):
        raise ValueError("Master's share m must be in [0, 1].")

    r = normalize_dist(r)
    s = normalize_dist(s)

    num_master = int(round(N * m))
    num_non_master = N - num_master

    non_counts = allocate_counts(num_non_master, r)
    master_counts = allocate_counts(num_master, s)

    all_counts = non_counts + master_counts
    all_weights = WEIGHTS + WEIGHTS

    draws1 = min(REGULAR_CAP, N)
    p1_all = draw_probs_by_group(all_counts, all_weights, draws1)
    p1_non = p1_all[:4]
    p1_master = p1_all[4:]

    master_remaining = [c * (1.0 - p) for c, p in zip(master_counts, p1_master)]
    draws2 = min(MASTER_CAP, sum(master_remaining))
    p2_master_cond = draw_probs_by_group(master_remaining, WEIGHTS, draws2)

    p_master_final = [
        p1 + (1.0 - p1) * p2
        for p1, p2 in zip(p1_master, p2_master_cond)
    ]

    p_non_final = p1_non[:]

    non_results = {
        f"Level {lv}": GroupResult(
            count=non_counts[i],
            regular_prob=p1_non[i],
            final_prob=p_non_final[i],
            master_cap_cond=None,
        )
        for i, lv in enumerate(LEVELS)
    }
    master_results = {
        f"Level {lv}": GroupResult(
            count=master_counts[i],
            regular_prob=p1_master[i],
            final_prob=p_master_final[i],
            master_cap_cond=p2_master_cond[i],
        )
        for i, lv in enumerate(LEVELS)
    }

    total_selected = (
        sum(non_counts[i] * p_non_final[i] for i in range(4))
        + sum(master_counts[i] * p_master_final[i] for i in range(4))
    )
    overall_prob = total_selected / N

    return {
        "N": N,
        "m": m,
        "non_counts": non_counts,
        "master_counts": master_counts,
        "non_results": non_results,
        "master_results": master_results,
        "overall_prob": overall_prob,
        "regular_draws": draws1,
        "master_draws": draws2,
    }


def estimate_h1b_unweighted(
    N: int,
    m: float,
    r: Sequence[float],
    s: Sequence[float],
) -> Dict[str, object]:
    if N <= 0:
        raise ValueError("N must be a positive integer.")
    if not (0.0 <= m <= 1.0):
        raise ValueError("Master's share m must be in [0, 1].")

    r = normalize_dist(r)
    s = normalize_dist(s)

    num_master = int(round(N * m))
    num_non_master = N - num_master

    non_counts = allocate_counts(num_non_master, r)
    master_counts = allocate_counts(num_master, s)

    draws1 = float(min(REGULAR_CAP, N))
    p1 = draws1 / float(N) if N > 0 else 0.0

    m_rem = float(num_master) * (1.0 - p1)
    draws2 = float(min(MASTER_CAP, m_rem)) if m_rem > 0 else 0.0
    p2_cond = min(1.0, draws2 / m_rem) if m_rem > 1e-15 else 0.0

    p_non_final = p1
    p_master_final = p1 + (1.0 - p1) * p2_cond

    non_results = {
        f"Level {lv}": GroupResult(
            count=non_counts[i],
            regular_prob=p1,
            final_prob=p_non_final,
            master_cap_cond=None,
        )
        for i, lv in enumerate(LEVELS)
    }
    master_results = {
        f"Level {lv}": GroupResult(
            count=master_counts[i],
            regular_prob=p1,
            final_prob=p_master_final,
            master_cap_cond=p2_cond,
        )
        for i, lv in enumerate(LEVELS)
    }

    total_selected = (
        float(num_non_master) * p_non_final
        + float(num_master) * p_master_final
    )
    overall_prob = total_selected / float(N)

    return {
        "N": N,
        "m": m,
        "non_counts": non_counts,
        "master_counts": master_counts,
        "non_results": non_results,
        "master_results": master_results,
        "overall_prob": overall_prob,
        "regular_draws": draws1,
        "master_draws": draws2,
    }


def format_pct(x: float) -> str:
    return f"{x * 100:.2f}%"


def print_cli_report(res: Dict[str, object], weighted: bool = True) -> None:
    print("=" * 72)
    title = (
        "H-1B lottery estimates (wage-weighted)"
        if weighted
        else "H-1B lottery estimates (unweighted two-pool)"
    )
    print(title)
    print("=" * 72)
    print(f"Total registrations N: {res['N']}")
    print(f"Master's-eligible share m: {res['m']:.4f}")
    print(f"Regular cap (round 1) slots: {int(res['regular_draws'])}")
    print(f"Master's cap (round 2) effective slots: {int(round(res['master_draws']))}")
    print("-" * 72)
    print("Non-master's — selection probability by wage level")
    for lv, g in res["non_results"].items():
        assert isinstance(g, GroupResult)
        print(f"{lv:>8} | count={g.count:>8} | P={format_pct(g.final_prob):>8}")
    print("-" * 72)
    print("Master's-eligible — selection probability by wage level")
    for lv, g in res["master_results"].items():
        assert isinstance(g, GroupResult)
        print(f"{lv:>8} | count={g.count:>8} | P={format_pct(g.final_prob):>8}")
    print("-" * 72)
    print(f"Overall selection probability: {format_pct(res['overall_prob'])}")
    print("=" * 72)


def run_dashboard() -> None:
    try:
        import gradio as gr
        import pandas as pd
    except Exception as e:
        raise SystemExit(
            "Dashboard dependencies missing. Install with:\n"
            "  pip install gradio pandas\n"
            f"Error: {e}"
        )

    def _dataframe_from_result(
        res: Dict[str, object],
        r_pct: List[float],
        s_pct: List[float],
        show_mode: str,
    ):
        rows = []
        for lv, g in res["non_results"].items():
            assert isinstance(g, GroupResult)
            idx = int(lv.split()[-1]) - 1
            row: Dict[str, object] = {
                "Category": "Non-master's",
                "Wage level": lv,
                "Input share": f"{r_pct[idx]:.2f}%",
                "Count": g.count,
                "Round 1 (Regular cap)": f"{g.regular_prob * 100:.2f}%",
                "Round 2 (Master cap)": "N/A",
                "Probability": f"{g.final_prob * 100:.2f}%",
            }
            rows.append(row)
        for lv, g in res["master_results"].items():
            assert isinstance(g, GroupResult)
            idx = int(lv.split()[-1]) - 1
            mc = g.master_cap_cond
            row = {
                "Category": "Master's-eligible",
                "Wage level": lv,
                "Input share": f"{s_pct[idx]:.2f}%",
                "Count": g.count,
                "Round 1 (Regular cap)": f"{g.regular_prob * 100:.2f}%",
                "Round 2 (Master cap)": (
                    f"{mc * 100:.2f}%"
                    if mc is not None
                    else "N/A"
                ),
                "Probability": f"{g.final_prob * 100:.2f}%",
            }
            rows.append(row)
        df = pd.DataFrame(rows)
        if show_mode == SHOW_MODE_SIMPLE:
            df = df.drop(
                columns=["Round 1 (Regular cap)", "Round 2 (Master cap)"],
                errors="ignore",
            )
        return df

    def compute(
        N: int,
        m: float,
        r1: float,
        r2: float,
        r3: float,
        r4: float,
        s1: float,
        s2: float,
        s3: float,
        s4: float,
        show_mode: str,
    ):
        r_pct = [r1, r2, r3, r4]
        s_pct = [s1, s2, s3, s4]

        if any(x is None for x in [N, m, *r_pct, *s_pct]):
            raise gr.Error("Please fill in all inputs.")
        if any(x < 0 for x in r_pct + s_pct):
            raise gr.Error("Wage-level shares cannot be negative.")

        if abs(sum(r_pct) - 100.0) > 0.2:
            raise gr.Error(
                f"Non-master's shares must sum to about 100%; current sum is {sum(r_pct):.2f}%."
            )
        if abs(sum(s_pct) - 100.0) > 0.2:
            raise gr.Error(
                f"Master's-eligible shares must sum to about 100%; current sum is {sum(s_pct):.2f}%."
            )

        res = estimate_h1b(
            int(N),
            float(m),
            [x / 100.0 for x in r_pct],
            [x / 100.0 for x in s_pct],
        )

        return _dataframe_from_result(res, r_pct, s_pct, show_mode)

    def compute_unweighted(
        N: int,
        m: float,
        r1: float,
        r2: float,
        r3: float,
        r4: float,
        s1: float,
        s2: float,
        s3: float,
        s4: float,
        show_mode: str,
    ):
        r_pct = [r1, r2, r3, r4]
        s_pct = [s1, s2, s3, s4]

        if any(x is None for x in [N, m, *r_pct, *s_pct]):
            raise gr.Error("Please fill in all inputs.")
        if any(x < 0 for x in r_pct + s_pct):
            raise gr.Error("Wage-level shares cannot be negative.")

        if abs(sum(r_pct) - 100.0) > 0.2:
            raise gr.Error(
                f"Non-master's shares must sum to about 100%; current sum is {sum(r_pct):.2f}%."
            )
        if abs(sum(s_pct) - 100.0) > 0.2:
            raise gr.Error(
                f"Master's-eligible shares must sum to about 100%; current sum is {sum(s_pct):.2f}%."
            )

        res = estimate_h1b_unweighted(
            int(N),
            float(m),
            [x / 100.0 for x in r_pct],
            [x / 100.0 for x in s_pct],
        )

        return _dataframe_from_result(res, r_pct, s_pct, show_mode)

    with gr.Blocks(
        title="H-1B lottery probability",
        css="""
        .banner-wrap {
            display: none !important;
        }
        footer,
        gradio-app footer,
        footer[aria-label="Gradio footer navigation"] {
            display: none !important;
            visibility: hidden !important;
            height: 0 !important;
            min-height: 0 !important;
            padding: 0 !important;
            margin: 0 !important;
            overflow: hidden !important;
        }
        footer .built-with,
        footer .divider {
            display: none !important;
        }
        """,
        js="""
        () => {
            const removeFooter = () => {
                document
                    .querySelectorAll('footer[aria-label="Gradio footer navigation"]')
                    .forEach((el) => el.remove());
            };
            removeFooter();
            setTimeout(removeFooter, 200);
            setTimeout(removeFooter, 1000);
        }
        """,
    ) as demo:
        gr.Markdown("## H-1B lottery probability")
        gr.Markdown(
            "Educational estimate only; not legal advice. Results depend on inputs and simplifying assumptions."
        )

        with gr.Row():
            N = gr.Number(value=336153, label="Total registrations N", precision=0)
            m = gr.Slider(
                0,
                1,
                value=0.3557,
                step=0.0001,
                label="Master's-eligible share m",
            )

        gr.Markdown("### Non-master's wage level distribution (%)")
        with gr.Row():
            r1 = gr.Number(value=20, label="r1 (Level 1, %)")
            r2 = gr.Number(value=61, label="r2 (Level 2, %)")
            r3 = gr.Number(value=13, label="r3 (Level 3, %)")
            r4 = gr.Number(value=6, label="r4 (Level 4, %)")

        gr.Markdown("### Master's-eligible wage level distribution (%)")
        with gr.Row():
            s1 = gr.Number(value=35, label="s1 (Level 1, %)")
            s2 = gr.Number(value=50, label="s2 (Level 2, %)")
            s3 = gr.Number(value=11, label="s3 (Level 3, %)")
            s4 = gr.Number(value=4, label="s4 (Level 4, %)")

        show_mode = gr.Radio(
            choices=[SHOW_MODE_FULL, SHOW_MODE_SIMPLE],
            value=SHOW_MODE_FULL,
            label="Table columns",
            info=(
                "Round 2 (Master cap) is conditional: P(selected in round 2 | not selected in round 1). "
                "Non-master's applicants do not enter round 2."
            ),
        )

        inputs = [N, m, r1, r2, r3, r4, s1, s2, s3, s4, show_mode]

        with gr.Tabs():
            with gr.Tab("Wage-weighted"):
                gr.Markdown(
                    "Level 1–4 weights 1/2/3/4. Round 1: regular cap; round 2: master's cap for remaining eligible."
                )
                btn_w = gr.Button("Compute (weighted)")
                out_w = gr.Dataframe(
                    label="Results by group and wage level",
                    interactive=False,
                )
                btn_w.click(fn=compute, inputs=inputs, outputs=[out_w])

            with gr.Tab("Unweighted (legacy two-pool)"):
                gr.Markdown(
                    "No wage weighting: uniform random draw in round 1; then uniform draw among "
                    "remaining master's-eligible in round 2."
                )
                btn_u = gr.Button("Compute (unweighted)")
                out_u = gr.Dataframe(
                    label="Results by group and wage level",
                    interactive=False,
                )
                btn_u.click(fn=compute_unweighted, inputs=inputs, outputs=[out_u])

    demo.launch(inbrowser=True, share=False, pwa=False)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="H-1B lottery probability estimator (CLI + optional Gradio dashboard)"
    )
    parser.add_argument("--N", type=int, help="Total registrations")
    parser.add_argument("--m", type=float, help="Master's-eligible share (0–1)")
    parser.add_argument(
        "--r",
        nargs=4,
        type=float,
        metavar=("r1", "r2", "r3", "r4"),
        help="Non-master's Level 1–4 distribution",
    )
    parser.add_argument(
        "--s",
        nargs=4,
        type=float,
        metavar=("s1", "s2", "s3", "s4"),
        help="Master's-eligible Level 1–4 distribution",
    )
    parser.add_argument(
        "--dashboard",
        action="store_true",
        help="Launch local Gradio dashboard",
    )
    parser.add_argument(
        "--unweighted",
        action="store_true",
        help="Unweighted two-pool lottery (no wage weights)",
    )
    return parser


def interactive_input() -> Tuple[int, float, List[float], List[float]]:
    print("Incomplete CLI arguments; entering interactive mode.")
    N = int(input("Total registrations N: ").strip())
    m = float(input("Master's-eligible share m (0–1): ").strip())
    r = [
        float(x)
        for x in input("Non-master's r1 r2 r3 r4 (space-separated): ").split()
    ]
    s = [
        float(x)
        for x in input("Master's-eligible s1 s2 s3 s4 (space-separated): ").split()
    ]
    if len(r) != 4 or len(s) != 4:
        raise ValueError("r and s must each have 4 values.")
    return N, m, r, s


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.dashboard:
        run_dashboard()
        return

    if args.N is not None and args.m is not None and args.r is not None and args.s is not None:
        N, m, r, s = args.N, args.m, args.r, args.s
    else:
        N, m, r, s = interactive_input()

    if args.unweighted:
        res = estimate_h1b_unweighted(N, m, r, s)
        print_cli_report(res, weighted=False)
    else:
        res = estimate_h1b(N, m, r, s)
        print_cli_report(res, weighted=True)


if __name__ == "__main__":
    main()
