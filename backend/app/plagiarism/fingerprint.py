"""Shingle fingerprints over canonical tokens.

k-word shingles (default 6) of transliterated, homoglyph-normalised tokens.
Reference documents store *winnowed* hashes with their token position (a
fraction of all shingles, still guaranteeing detection of any common passage
of ``k + w - 1`` words); the checked document uses all its shingles.
"""
from __future__ import annotations

from app.analyzers.text_utils import stable_hash64

K = 6
WINNOW = 4


def shingles(tokens: list[str], stop: frozenset[str], k: int = K) -> list[tuple[int, int]]:
    """[(hash, start_index)] for shingles with at least two content words."""
    out = []
    for i in range(len(tokens) - k + 1):
        win = tokens[i : i + k]
        content = 0
        for t in win:
            if t not in stop and len(t) > 1:
                content += 1
        if content >= 2:
            out.append((stable_hash64(" ".join(win)), i))
    return out


def winnow(sh: list[tuple[int, int]], w: int = WINNOW) -> list[tuple[int, int]]:
    """Robust winnowing: keep the minimum hash of every window (with its position)."""
    if len(sh) <= w:
        return list(dict.fromkeys(sh))
    out: list[tuple[int, int]] = []
    last = None
    for i in range(len(sh) - w + 1):
        m = min(sh[i : i + w], key=lambda x: (x[0], -x[1]))
        if m != last:
            out.append(m)
            last = m
    return out
