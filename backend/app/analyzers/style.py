"""Section-level stylistic consistency analysis."""
from __future__ import annotations

from app.analyzers.ai_likelihood import STYLE_KEYS, compute_features, robust_stats
from app.analyzers.languages.base import LanguageProfile


def section_style_metrics(text: str, profile: LanguageProfile) -> dict[str, float]:
    f = compute_features(text, profile)
    return {k: round(float(f[k]), 4) for k in STYLE_KEYS if k in f}


def style_consistency(sections: list[dict], min_words: int = 150) -> dict:
    """Find sections whose style deviates strongly from the document's own norm.

    ``sections``: [{"order", "title", "word_count", "metrics": {...}}]
    Returns shifts between adjacent sections and outlier sections, with the
    metrics that drove the deviation.
    """
    usable = [s for s in sections if s["word_count"] >= min_words and s["metrics"]]
    if len(usable) < 3:
        return {"outliers": [], "shifts": [], "consistency": None, "note": "insufficient_sections"}
    stats = {k: robust_stats([s["metrics"][k] for s in usable if k in s["metrics"]]) for k in STYLE_KEYS}
    outliers = []
    zs_all = []
    for s in usable:
        zs = {k: (s["metrics"][k] - m) / d for k, (m, d) in stats.items() if k in s["metrics"]}
        top = sorted(zs.items(), key=lambda kv: -abs(kv[1]))[:3]
        dev = sum(abs(v) for _, v in top) / max(1, len(top))
        zs_all.append(dev)
        if dev > 2.5:
            outliers.append(
                {"order": s["order"], "title": s["title"], "deviation": round(dev, 2), "drivers": [{"metric": k, "z": round(v, 2)} for k, v in top]}
            )
    shifts = []
    for a, b in zip(usable, usable[1:]):
        diffs = {k: (b["metrics"][k] - a["metrics"][k]) / stats[k][1] for k in STYLE_KEYS if k in a["metrics"] and k in b["metrics"]}
        top = sorted(diffs.items(), key=lambda kv: -abs(kv[1]))[:3]
        mag = sum(abs(v) for _, v in top) / max(1, len(top))
        if mag > 3.0:
            shifts.append(
                {
                    "from_order": a["order"], "from_title": a["title"], "to_order": b["order"], "to_title": b["title"],
                    "magnitude": round(mag, 2), "drivers": [{"metric": k, "delta_z": round(v, 2)} for k, v in top],
                }
            )
    mean_dev = sum(zs_all) / len(zs_all)
    consistency = round(max(0.0, min(100.0, 100 - mean_dev * 20)), 1)
    return {"outliers": outliers, "shifts": shifts, "consistency": consistency, "note": None}
