"""Lightweight multilingual embeddings for paraphrase (semantic similarity) detection.

Backends (EMBEDDING_BACKEND):
  * ``model2vec`` — static multilingual embeddings (default model
    ``minishlab/potion-multilingual-128M``): no PyTorch, fast on CPU, ~0.5 GB
    RAM. Downloaded once into backend/data/models and cached.
  * ``hash``     — character n-gram hashing vectors. No download, works
    offline; detects re-worded text that keeps word stems (not translation).
  * ``auto``     — model2vec if it can be loaded, otherwise hash.

Vectors are L2-normalised and stored as float16. Vectors from different
backends are never compared (each stored vector carries its backend id).
"""
from __future__ import annotations

import logging
import os
import threading
from pathlib import Path

import numpy as np

from app.core.config import get_settings

log = logging.getLogger(__name__)
WINDOW = 50  # tokens per chunk (50/25 separated paraphrase from same-topic text best in tests)
STRIDE = 25
_lock = threading.Lock()
_backend = None


class HashBackend:
    dims = 512

    def __init__(self) -> None:
        from sklearn.feature_extraction.text import HashingVectorizer

        self.id = f"hash-char35-{self.dims}"
        self._vec = HashingVectorizer(analyzer="char_wb", ngram_range=(3, 5), n_features=self.dims, alternate_sign=False, norm="l2")

    def encode(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.dims), dtype=np.float32)
        return self._vec.transform(texts).toarray().astype(np.float32)


class Model2VecBackend:
    def __init__(self, model_name: str, cache_dir: Path) -> None:
        cache_dir.mkdir(parents=True, exist_ok=True)
        os.environ.setdefault("HF_HOME", str(cache_dir))
        from model2vec import StaticModel

        self._model = StaticModel.from_pretrained(model_name)
        probe = self._model.encode(["test"])
        self.dims = int(probe.shape[1])
        self.id = f"m2v:{model_name}"

    def encode(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.dims), dtype=np.float32)
        v = np.asarray(self._model.encode(texts), dtype=np.float32)
        n = np.linalg.norm(v, axis=1, keepdims=True)
        n[n == 0] = 1.0
        return v / n


def get_backend():
    """Load the configured backend once (thread-safe)."""
    global _backend
    with _lock:
        if _backend is not None:
            return _backend
        s = get_settings()
        choice = s.EMBEDDING_BACKEND
        # "auto" is decided once and remembered, so the corpus never mixes vector types
        # (e.g. first start offline -> hash; a later start online must not silently switch).
        marker = Path(s.MODEL_CACHE_DIR) / "embedding_backend.txt"
        if choice == "auto" and marker.exists():
            choice = marker.read_text().strip() or "auto"
        if choice in ("model2vec", "auto"):
            try:
                _backend = Model2VecBackend(s.EMBEDDING_MODEL, Path(s.MODEL_CACHE_DIR))
                log.info("embedding backend: %s (%d dims)", _backend.id, _backend.dims)
                _remember(marker, "model2vec", s.EMBEDDING_BACKEND)
                return _backend
            except Exception as exc:  # noqa: BLE001 - missing package, no network, bad model
                if choice == "model2vec":
                    log.warning("model2vec unavailable (%s); falling back to hash vectors", exc)
                else:
                    log.info("model2vec not available (%s); using hash vectors", exc.__class__.__name__)
        _backend = HashBackend()
        _remember(marker, "hash", s.EMBEDDING_BACKEND)
        return _backend


def _remember(marker: Path, choice: str, configured: str) -> None:
    if configured != "auto" or marker.exists():
        return
    try:
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(choice)
    except OSError:
        pass


def reset_backend() -> None:
    global _backend
    with _lock:
        _backend = None


def chunk_windows(tokens: list[str], window: int = WINDOW, stride: int = STRIDE) -> list[tuple[int, int]]:
    if len(tokens) < 20:
        return []
    spans = []
    i = 0
    while i < len(tokens):
        end = min(len(tokens), i + window)
        if end - i >= 20:
            spans.append((i, end))
        if end == len(tokens):
            break
        i += stride
    return spans


def to_blob(v: np.ndarray) -> bytes:
    return v.astype(np.float16).tobytes()


def from_blob(b: bytes, dims: int) -> np.ndarray:
    return np.frombuffer(b, dtype=np.float16).astype(np.float32).reshape(-1, dims)
