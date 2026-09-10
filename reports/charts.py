"""Server-rendered trend/control charts for the Certificate of Analysis.

The COA is rendered by xhtml2pdf, which converts static HTML/CSS to PDF —
it has no JavaScript engine, so the Chart.js line charts used on the
dashboard (dashboard/analytics_trend.html) can't be reused here. Instead we
draw each chart with matplotlib (headless "Agg" backend) and embed it as a
base64 PNG data URI, the same technique already used for the logo in
coa_context() (reports/views.py). Kept in its own module so the matplotlib
import — a real dependency, only needed for this one feature — stays out of
the request path for every other view.
"""

import base64
import statistics
from io import BytesIO

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from django.utils import timezone  # noqa: E402

from catalog.models import SpecLimit  # noqa: E402

# Palette matches the rest of the COA/dashboard (coa_pdf.html, analytics_trend.html)
# so the certificate reads as one system rather than mixing chart styles.
_INK = "#22232e"
_MUTED = "#6b6f80"
_LINE = "#333750"
_GRID = "#eef0f5"
_SPINE = "#d8d9e2"
_PASS = "#1f9d55"
_FAIL = "#c62a21"
_UNKNOWN = "#9a9dab"


def render_trend_chart_png(test_method, fuel_type, current_result=None):
    """Render a small trend/spec chart for a test method + fuel type.

    Plots every historical result for this exact (test_method, fuel_type)
    pair — not just this sample's — so the chart shows how this result
    compares to the fuel type's own testing history, with the real spec
    limit band drawn behind it. Returns a data: URI PNG, or None if there
    isn't at least one historical result to plot.
    """
    from labtests.models import TestResult

    results = list(
        TestResult.objects.filter(sample_test__test_method=test_method, sample_test__sample__fuel_type=fuel_type)
        .select_related("sample_test__sample")
        .order_by("entered_at")
    )
    if not results:
        return None

    values = [r.value for r in results]
    dates = [timezone.localtime(r.entered_at) for r in results]
    verdicts = [r.pass_fail for r in results]
    point_colors = [_PASS if v is True else _FAIL if v is False else _UNKNOWN for v in verdicts]

    current_idx = None
    if current_result is not None:
        for i, r in enumerate(results):
            if r.pk == current_result.pk:
                current_idx = i
                break

    spec = SpecLimit.objects.filter(test_method=test_method, fuel_type=fuel_type).first()
    min_v = spec.min_value if spec else None
    max_v = spec.max_value if spec else None

    x = list(range(len(values)))
    extent = list(values)
    if min_v is not None:
        extent.append(min_v)
    if max_v is not None:
        extent.append(max_v)
    lo, hi = min(extent), max(extent)
    pad = (hi - lo) * 0.18 if hi > lo else max(abs(hi) * 0.1, 1.0)
    ylo, yhi = lo - pad, hi + pad

    fig, ax = plt.subplots(figsize=(6.2, 1.9), dpi=165)
    fig.patch.set_facecolor("#ffffff")
    ax.set_facecolor("#ffffff")
    ax.set_ylim(ylo, yhi)

    # Real spec limit(s): shaded acceptable band + dashed boundary lines,
    # labeled directly rather than via a legend box (selective direct
    # labeling for a single-series chart at this size).
    if min_v is not None or max_v is not None:
        band_lo = min_v if min_v is not None else ylo
        band_hi = max_v if max_v is not None else yhi
        ax.axhspan(band_lo, band_hi, color=_PASS, alpha=0.07, zorder=0)
        if min_v is not None:
            ax.axhline(min_v, color=_LINE, linestyle=(0, (4, 3)), linewidth=1.0, zorder=1)
            ax.annotate(
                f"spec min {min_v:g}", xy=(x[-1], min_v), xytext=(3, 3), textcoords="offset points",
                fontsize=6.5, color=_MUTED, va="bottom", ha="right",
            )
        if max_v is not None:
            ax.axhline(max_v, color=_LINE, linestyle=(0, (4, 3)), linewidth=1.0, zorder=1)
            ax.annotate(
                f"spec max {max_v:g}", xy=(x[-1], max_v), xytext=(3, -3), textcoords="offset points",
                fontsize=6.5, color=_MUTED, va="top", ha="right",
            )

    ax.plot(x, values, color=_LINE, linewidth=1.5, zorder=2, solid_capstyle="round")
    ax.scatter(x, values, c=point_colors, s=24, zorder=3, edgecolors="#ffffff", linewidths=0.7)

    if current_idx is not None:
        ax.scatter(
            [x[current_idx]], [values[current_idx]], s=110, facecolors="none",
            edgecolors=_INK, linewidths=1.6, zorder=4,
        )
        ax.annotate(
            f"this sample — {values[current_idx]:g}",
            xy=(x[current_idx], values[current_idx]), xytext=(0, 9), textcoords="offset points",
            ha="center", fontsize=7.2, color=_INK, fontweight="bold", zorder=5,
        )

    # Thin the x tick labels so dates never collide at small print size.
    labels = [d.strftime("%d %b '%y") for d in dates]
    step = max(1, len(labels) // 6)
    ax.set_xticks(x[::step])
    ax.set_xticklabels(labels[::step], fontsize=6.3, color=_MUTED)
    ax.set_xlim(-0.5, len(x) - 0.5)

    ax.set_ylabel(test_method.unit or "", fontsize=7, color=_MUTED)
    ax.tick_params(axis="y", labelsize=6.5, colors=_MUTED, length=2)
    ax.tick_params(axis="x", length=2)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(_SPINE)
    ax.grid(axis="y", color=_GRID, linewidth=0.8, zorder=0)

    fig.tight_layout(pad=0.5)
    buf = BytesIO()
    fig.savefig(buf, format="png", facecolor=fig.get_facecolor())
    plt.close(fig)
    buf.seek(0)
    encoded = base64.b64encode(buf.read()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def build_trend_charts(rows):
    """Attach a rendered trend-chart data URI to each COA row that has a result.

    `rows` is the list built in reports.views.coa_context() — dicts with
    test_method/result/limit/verdict. Mutates and returns the same rows so
    it can be called as `rows = build_trend_charts(rows)` from that helper.
    """
    for row in rows:
        result = row.get("result")
        if result is None:
            row["chart"] = None
            continue
        fuel_type = result.sample_test.sample.fuel_type
        row["chart"] = render_trend_chart_png(row["test_method"], fuel_type, current_result=result)
    return rows
