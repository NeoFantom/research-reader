#!/usr/bin/env python3
"""Generate the example figures: a small Kuramoto-model simulation drawn as SVG.

Pure standard library so the example stays reproducible anywhere:
    python3 make_figures.py          # writes figures/*.svg and figures/data.json
The research topic is fictional teaching material; the numbers are real outputs of this script.
"""

from __future__ import annotations

import cmath
import json
import math
import random
from pathlib import Path

OUT = Path(__file__).resolve().parent / "figures"
N, GAMMA, DT, T_END, SEED = 200, 0.5, 0.05, 100.0, 7
K_VALUES = [round(0.2 * i, 1) for i in range(0, 21)]  # 0.0 … 4.0
K_C = 2 * GAMMA  # critical coupling for a Lorentzian frequency distribution

INK, MUTED, GRID, ACCENT, ACCENT_2, WARM = "#121715", "#68756f", "#d9e3df", "#008566", "#5aa88f", "#b5651d"
FONT = "IBM Plex Sans, PingFang SC, Microsoft YaHei, sans-serif"


def frequencies() -> list[float]:
    """Deterministic Lorentzian quantiles: no sampling noise in the frequency set."""
    return [GAMMA * math.tan(math.pi * ((i + 0.5) / N - 0.5)) for i in range(N)]


def simulate(k: float, omega: list[float], record: bool = False) -> tuple[float, list[float], list[float]]:
    rng = random.Random(SEED)
    theta = [rng.uniform(-math.pi, math.pi) for _ in range(N)]
    steps = int(T_END / DT)
    series, tail = [], []
    for step in range(steps):
        z = sum(cmath.exp(1j * th) for th in theta) / N
        r, psi = abs(z), cmath.phase(z)
        if record and step % 10 == 0:
            series.append(r)
        if step >= int(0.6 * steps):
            tail.append(r)
        theta = [th + DT * (w + k * r * math.sin(psi - th)) for th, w in zip(theta, omega)]
    return sum(tail) / len(tail), series, theta


def frame(w: int, h: int, body: str, title: str) -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" role="img" aria-label="{title}">'
            f'<rect width="{w}" height="{h}" fill="#fff"/><g font-family="{FONT}" font-size="14" fill="{INK}">{body}</g></svg>\n')


def axes(x0: float, y0: float, w: float, h: float, xmax: float, ymax: float, xlabel: str, ylabel: str, xticks: list[float], yticks: list[float]) -> tuple[str, callable]:
    def px(x: float, y: float) -> tuple[float, float]:
        return x0 + w * x / xmax, y0 + h - h * y / ymax
    parts = []
    for t in yticks:
        _, y = px(0, t)
        parts.append(f'<line x1="{x0}" y1="{y:.1f}" x2="{x0 + w}" y2="{y:.1f}" stroke="{GRID}"/>'
                     f'<text x="{x0 - 10}" y="{y + 5:.1f}" text-anchor="end" fill="{MUTED}">{t:g}</text>')
    for t in xticks:
        x, _ = px(t, 0)
        parts.append(f'<line x1="{x:.1f}" y1="{y0 + h}" x2="{x:.1f}" y2="{y0 + h + 6}" stroke="{MUTED}"/>'
                     f'<text x="{x:.1f}" y="{y0 + h + 24}" text-anchor="middle" fill="{MUTED}">{t:g}</text>')
    parts.append(f'<line x1="{x0}" y1="{y0 + h}" x2="{x0 + w}" y2="{y0 + h}" stroke="{INK}"/>'
                 f'<line x1="{x0}" y1="{y0}" x2="{x0}" y2="{y0 + h}" stroke="{INK}"/>'
                 f'<text x="{x0 + w / 2}" y="{y0 + h + 50}" text-anchor="middle">{xlabel}</text>'
                 f'<text transform="translate({x0 - 52} {y0 + h / 2}) rotate(-90)" text-anchor="middle">{ylabel}</text>')
    return "".join(parts), px


def polyline(points: list[tuple[float, float]], color: str, width: float = 2.5, dash: str = "") -> str:
    d = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
    extra = f' stroke-dasharray="{dash}"' if dash else ""
    return f'<polyline points="{d}" fill="none" stroke="{color}" stroke-width="{width}"{extra}/>'


def fig_order_parameter(rows: list[dict]) -> str:
    grid, px = axes(90, 30, 640, 330, 4.0, 1.0, "耦合强度 K", "序参量 r（稳态均值）", [0, 1, 2, 3, 4], [0, 0.25, 0.5, 0.75, 1])
    theory = [px(K_C + i * 0.01, math.sqrt(1 - K_C / (K_C + i * 0.01))) for i in range(0, 301)]
    flat = [px(0, 0), px(K_C, 0)]
    dots = "".join(f'<circle cx="{px(r["K"], r["r"])[0]:.1f}" cy="{px(r["K"], r["r"])[1]:.1f}" r="5" fill="{ACCENT}"/>' for r in rows)
    kc_x = px(K_C, 0)[0]
    marks = (f'<line x1="{kc_x:.1f}" y1="30" x2="{kc_x:.1f}" y2="360" stroke="{WARM}" stroke-dasharray="4 4"/>'
             f'<text x="{kc_x + 8:.1f}" y="50" fill="{WARM}">K_c = 2γ = {K_C:g}</text>')
    legend = (f'<g transform="translate(560 270)"><circle cx="0" cy="0" r="5" fill="{ACCENT}"/><text x="14" y="5">数值模拟 N={N}</text>'
              f'<line x1="-8" y1="24" x2="8" y2="24" stroke="{INK}" stroke-width="2" stroke-dasharray="6 4"/><text x="14" y="29">平均场理论</text></g>')
    body = grid + marks + polyline(flat, INK, 2, "6 4") + polyline(theory, INK, 2, "6 4") + dots + legend
    return frame(780, 420, body, "order parameter versus coupling strength")


def fig_time_series(series: dict[float, list[float]]) -> str:
    grid, px = axes(90, 30, 640, 300, T_END, 1.0, "时间 t", "序参量 r(t)", [0, 20, 40, 60, 80, 100], [0, 0.5, 1])
    colors = {0.5: MUTED, 1.5: ACCENT_2, 3.0: ACCENT}
    lines, legend = [], []
    for n, (k, s) in enumerate(series.items()):
        pts = [px(i * 10 * DT, v) for i, v in enumerate(s)]
        lines.append(polyline(pts, colors[k], 2))
        legend.append(f'<line x1="{560}" y1="{196 + 22 * n}" x2="{584}" y2="{196 + 22 * n}" stroke="{colors[k]}" stroke-width="3"/><text x="594" y="{201 + 22 * n}">K = {k:g}</text>')
    return frame(780, 390, grid + "".join(lines) + "".join(legend), "order parameter time series")


def fig_phases(snapshots: dict[float, list[float]]) -> str:
    parts = []
    for n, (k, theta) in enumerate(snapshots.items()):
        cx, cy, rad = 190 + n * 400, 200, 140
        z = sum(cmath.exp(1j * t) for t in theta) / N
        parts.append(f'<circle cx="{cx}" cy="{cy}" r="{rad}" fill="none" stroke="{GRID}" stroke-width="2"/>')
        for t in theta:
            parts.append(f'<circle cx="{cx + rad * math.cos(t):.1f}" cy="{cy - rad * math.sin(t):.1f}" r="3.2" fill="{ACCENT}" fill-opacity=".45"/>')
        ex, ey = cx + rad * z.real, cy - rad * z.imag
        parts.append(f'<line x1="{cx}" y1="{cy}" x2="{ex:.1f}" y2="{ey:.1f}" stroke="{WARM}" stroke-width="3"/><circle cx="{ex:.1f}" cy="{ey:.1f}" r="5" fill="{WARM}"/>')
        parts.append(f'<text x="{cx}" y="{cy + rad + 36}" text-anchor="middle">K = {k:g} · r = {abs(z):.2f}</text>')
    return frame(780, 400, "".join(parts), "phase snapshots on the unit circle")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    omega = frequencies()
    rows = []
    for k in K_VALUES:
        r, _, _ = simulate(k, omega)
        rows.append({"K": k, "r": round(r, 4)})
        print(f"K={k:.1f}  r={r:.3f}")
    series, snaps = {}, {}
    for k in (0.5, 1.5, 3.0):
        _, s, theta = simulate(k, omega, record=True)
        series[k] = s
        if k in (0.5, 3.0):
            snaps[k] = theta
    (OUT / "order-parameter.svg").write_text(fig_order_parameter(rows), encoding="utf-8")
    (OUT / "time-series.svg").write_text(fig_time_series(series), encoding="utf-8")
    (OUT / "phase-snapshots.svg").write_text(fig_phases(snaps), encoding="utf-8")
    meta = {"N": N, "gamma": GAMMA, "dt": DT, "t_end": T_END, "seed": SEED, "K_c": K_C, "sweep": rows}
    (OUT / "data.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
