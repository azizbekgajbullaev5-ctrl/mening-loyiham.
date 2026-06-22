"""Premium maqolalar uchun matplotlib bilan diagramma rasmlari chizish.

Claude qaytargan diagramma ma'lumotlaridan (dict) PNG rasm tuzadi.
Diagramma sarlavhasi va o'qlar nomi maqolaning asosiy tili (bitta til)da bo'ladi.
"""
from __future__ import annotations

import io
import logging

import matplotlib

# Serverda displeysiz (headless) ishlash uchun — har qanday importdan oldin
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

logger = logging.getLogger(__name__)

# Diagramma turlari uchun qo'llab-quvvatlanadigan qiymatlar
_SUPPORTED = {"bar", "pie", "line"}


def _coerce_values(values: list) -> list[float]:
    out: list[float] = []
    for v in values:
        try:
            out.append(float(v))
        except (TypeError, ValueError):
            out.append(0.0)
    return out


def render_chart(chart: dict) -> io.BytesIO | None:
    """Bitta diagramma dict'idan PNG oqimini qaytaradi; xato bo'lsa None.

    Kutilgan tuzilma:
        {
          "type": "bar" | "pie" | "line",
          "title": "...",
          "labels": ["A", "B", ...],
          "values": [1.0, 2.0, ...],
          "x_label": "...",   # ixtiyoriy (bar/line uchun)
          "y_label": "..."    # ixtiyoriy (bar/line uchun)
        }
    """
    try:
        ctype = (chart.get("type") or "bar").lower()
        if ctype not in _SUPPORTED:
            ctype = "bar"
        labels = [str(x) for x in (chart.get("labels") or [])]
        values = _coerce_values(chart.get("values") or [])
        if not labels or not values:
            return None
        # Mos kelmasa — qisqaroq uzunlikka kesamiz
        n = min(len(labels), len(values))
        labels, values = labels[:n], values[:n]

        fig, ax = plt.subplots(figsize=(7, 4.2), dpi=150)

        if ctype == "pie":
            ax.pie(values, labels=labels, autopct="%1.1f%%", startangle=90)
            ax.axis("equal")
        elif ctype == "line":
            ax.plot(labels, values, marker="o", color="#2563eb")
            ax.grid(True, linestyle="--", alpha=0.4)
            if chart.get("x_label"):
                ax.set_xlabel(str(chart["x_label"]))
            if chart.get("y_label"):
                ax.set_ylabel(str(chart["y_label"]))
        else:  # bar
            ax.bar(labels, values, color="#2563eb")
            ax.grid(True, axis="y", linestyle="--", alpha=0.4)
            if chart.get("x_label"):
                ax.set_xlabel(str(chart["x_label"]))
            if chart.get("y_label"):
                ax.set_ylabel(str(chart["y_label"]))

        if chart.get("title"):
            ax.set_title(str(chart["title"]), fontsize=12, fontweight="bold")

        if ctype != "pie" and any(len(lbl) > 6 for lbl in labels):
            plt.setp(ax.get_xticklabels(), rotation=30, ha="right")

        fig.tight_layout()
        buf = io.BytesIO()
        fig.savefig(buf, format="png", bbox_inches="tight")
        plt.close(fig)
        buf.seek(0)
        return buf
    except Exception:  # noqa: BLE001
        logger.warning("Diagramma chizishda xatolik", exc_info=True)
        try:
            plt.close("all")
        except Exception:  # noqa: BLE001
            pass
        return None
