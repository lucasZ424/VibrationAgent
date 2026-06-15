"""Embedding generation with explicit deterministic fallback."""
from __future__ import annotations

import hashlib
import importlib
import os
from collections import OrderedDict
from collections.abc import Callable, Sequence
from functools import lru_cache
from pathlib import Path
from typing import Any

from vibration_agent.config import EmbeddingSettings, Settings, load
from vibration_agent.llm._guards import LiveProviderDisabledError, pytest_guard_active
from vibration_agent.schemas import EmbeddingRecord

ModelLoader = Callable[[EmbeddingSettings], Any]
_CACHE_MAX_SIZE = 4096
_EMBEDDING_CACHE: OrderedDict[tuple[str, str, str, str | None], EmbeddingRecord] = OrderedDict()


class EmbeddingModelNotConfigured(RuntimeError):
    pass


def text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def clear_embedding_cache() -> None:
    _EMBEDDING_CACHE.clear()


def _settings_cache_prefix(settings: EmbeddingSettings) -> tuple[str, str, str | None]:
    return (settings.provider, settings.model_name, settings.model_version)


def _cache_key(text: str, settings: EmbeddingSettings) -> tuple[str, str, str, str | None]:
    provider, model_name, model_version = _settings_cache_prefix(settings)
    return (text_hash(text), provider, model_name, model_version)


def _cache_get(text: str, settings: EmbeddingSettings) -> EmbeddingRecord | None:
    key = _cache_key(text, settings)
    record = _EMBEDDING_CACHE.get(key)
    if record is None:
        return None
    _EMBEDDING_CACHE.move_to_end(key)
    return record.model_copy(deep=True)


def _cache_put(text: str, settings: EmbeddingSettings, record: EmbeddingRecord) -> None:
    key = _cache_key(text, settings)
    _EMBEDDING_CACHE[key] = record.model_copy(deep=True)
    _EMBEDDING_CACHE.move_to_end(key)
    while len(_EMBEDDING_CACHE) > _CACHE_MAX_SIZE:
        _EMBEDDING_CACHE.popitem(last=False)


def _default_settings() -> Settings:
    return load()


@lru_cache(maxsize=8)
def _load_sentence_transformer(model_name: str, local_files_only: bool) -> Any:
    try:
        from sentence_transformers import SentenceTransformer  # type: ignore
    except ModuleNotFoundError as exc:
        raise RuntimeError("sentence-transformers is not installed.") from exc
    return SentenceTransformer(model_name, local_files_only=local_files_only)


def _load_model(settings: EmbeddingSettings) -> Any:
    if settings.provider == "openai":
        return _load_openai_client(settings)
    if settings.provider != "sentence_transformers":
        raise RuntimeError(f"Unsupported embedding provider: {settings.provider}")
    if settings.local_files_only and not Path(settings.model_name).expanduser().exists():
        raise EmbeddingModelNotConfigured(f"Local embedding model path not found: {settings.model_name}")
    if pytest_guard_active():
        raise LiveProviderDisabledError("Live sentence-transformer embedding model loads are forbidden during pytest.")
    return _load_sentence_transformer(settings.model_name, settings.local_files_only)


def _load_openai_client(settings: EmbeddingSettings) -> Any:
    if pytest_guard_active():
        raise LiveProviderDisabledError("Live OpenAI embedding clients are forbidden during pytest.")
    api_key = os.getenv(settings.api_key_env)
    if not api_key:
        raise RuntimeError(f"Missing OpenAI API key env var: {settings.api_key_env}")
    openai = importlib.import_module("openai")
    return openai.OpenAI(api_key=api_key, timeout=settings.timeout)


def _encode_batch(model: Any, batch: Sequence[str], settings: EmbeddingSettings) -> list[list[float]]:
    if settings.provider == "openai":
        return _encode_openai_batch(model, batch, settings)
    encoded = model.encode(list(batch), convert_to_numpy=False, normalize_embeddings=True)
    vectors: list[list[float]] = []
    for item in encoded:
        if hasattr(item, "tolist"):
            item = item.tolist()
        vectors.append([float(value) for value in item])
    return vectors


def _encode_openai_batch(model: Any, batch: Sequence[str], settings: EmbeddingSettings) -> list[list[float]]:
    response = model.embeddings.create(model=settings.model_name, input=list(batch))
    data = response.get("data") if isinstance(response, dict) else getattr(response, "data", None)
    if data is None and hasattr(response, "model_dump"):
        dumped = response.model_dump(mode="python")
        data = dumped.get("data") if isinstance(dumped, dict) else None
    if not isinstance(data, list):
        raise RuntimeError("OpenAI embeddings response missing data list.")
    vectors: list[list[float]] = []
    for item in data:
        embedding = item.get("embedding") if isinstance(item, dict) else getattr(item, "embedding", None)
        if embedding is None:
            raise RuntimeError("OpenAI embeddings response item missing embedding.")
        vectors.append([float(value) for value in embedding])
    if len(vectors) != len(batch):
        raise RuntimeError("OpenAI embeddings response length did not match request batch.")
    return vectors


def _fallback_record(text: str, settings: EmbeddingSettings, warning: str | None) -> EmbeddingRecord:
    return EmbeddingRecord(
        text_hash=text_hash(text),
        vector=[],
        dimension=0,
        model_name=settings.model_name,
        model_version=settings.model_version,
        provider="fallback_token_features",
        warnings=[warning] if warning else [],
    )


def _is_default_cold_start(exc: Exception, settings: EmbeddingSettings) -> bool:
    return (
        isinstance(exc, EmbeddingModelNotConfigured)
        and settings.local_files_only
        and settings.model_name == EmbeddingSettings().model_name
    )


def embed_texts(
    texts: Sequence[str],
    *,
    batch_size: int | None = None,
    settings: Settings | EmbeddingSettings | None = None,
    model_loader: ModelLoader | None = None,
) -> list[EmbeddingRecord]:
    """Embed texts in batches, deduping repeated text within the call."""
    active_settings = settings.embeddings if isinstance(settings, Settings) else settings
    embedding_settings = active_settings or _default_settings().embeddings
    final_batch_size = batch_size or embedding_settings.batch_size
    if final_batch_size <= 0:
        raise ValueError("batch_size must be greater than 0")

    unique_texts = list(dict.fromkeys(str(text) for text in texts))
    by_text: dict[str, EmbeddingRecord] = {}
    if not unique_texts:
        return []

    if not embedding_settings.enabled:
        by_text = {text: _fallback_record(text, embedding_settings, None) for text in unique_texts}
        return [by_text[str(text)] for text in texts]

    try:
        missing_texts: list[str] = []
        for text in unique_texts:
            cached = _cache_get(text, embedding_settings)
            if cached is None:
                missing_texts.append(text)
            else:
                by_text[text] = cached
        if not missing_texts:
            return [by_text[str(text)] for text in texts]

        model = (model_loader or _load_model)(embedding_settings)
        for start in range(0, len(missing_texts), final_batch_size):
            batch = missing_texts[start : start + final_batch_size]
            vectors = _encode_batch(model, batch, embedding_settings)
            for text, vector in zip(batch, vectors, strict=True):
                record = EmbeddingRecord(
                    text_hash=text_hash(text),
                    vector=vector,
                    dimension=len(vector),
                    model_name=embedding_settings.model_name,
                    model_version=embedding_settings.model_version,
                    provider=embedding_settings.provider,
                    warnings=[],
                )
                by_text[text] = record
                _cache_put(text, embedding_settings, record)
    except Exception as exc:
        if not embedding_settings.fallback_to_token_features:
            raise
        warning = None
        if not _is_default_cold_start(exc, embedding_settings):
            warning = f"Embedding model unavailable; using token-feature fallback: {type(exc).__name__}: {exc}"
        by_text = {text: _fallback_record(text, embedding_settings, warning) for text in unique_texts}

    return [by_text[str(text)] for text in texts]
