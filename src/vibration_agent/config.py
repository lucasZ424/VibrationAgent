"""Runtime configuration for vibration_agent.

Configuration is loaded from configs/*.yaml and then overridden by environment
variables. Code should depend on Settings instead of reading environment values
or YAML files directly.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from .schemas import UserMode


class PathSettings(BaseModel):
    workspace: Path
    data_dir: Path
    raw_dir: Path
    ocr_dir: Path
    extracted_dir: Path
    chunks_dir: Path
    embeddings_dir: Path
    exports_dir: Path


class ClassifySettings(BaseModel):
    ocr_text_density_threshold: float = Field(default=0.2, ge=0.0)


class DatabaseSettings(BaseModel):
    postgres_url: str = ""
    postgres_enabled: bool = False
    postgres_timeout: float = Field(default=2.0, gt=0.0)
    qdrant_enabled: bool = False
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str = ""
    qdrant_collection: str = "chunks"
    qdrant_vector_size: int = Field(default=384, ge=1)
    qdrant_timeout: float = Field(default=2.0, gt=0.0)
    redis_url: str = "redis://localhost:6379/0"


class OcrSettings(BaseModel):
    primary: str = "paddleocr"
    fallback: str = "tesseract"
    paddleocr_lang: str = "ch"
    tesseract_langs: str = "chi_sim+eng+osd"
    low_confidence_threshold: float = Field(default=0.6, ge=0.0, le=1.0)
    render_dpi: int = Field(default=220, ge=72)


class ChunkingSettings(BaseModel):
    target_tokens: int = Field(default=600, ge=1)
    overlap_tokens: int = Field(default=60, ge=0)
    preserve_anchors: bool = True


class RoutingSettings(BaseModel):
    default_owner: str = "gpt"
    opus_difficulties: list[str] = Field(default_factory=lambda: ["extreme"])
    repeated_failure_threshold: int = Field(default=2, ge=1)
    explicit_extreme_markers: list[str] = Field(default_factory=lambda: ["extreme", "opus", "senior_supervisor"])


class RetrievalSettings(BaseModel):
    mode: str = "hybrid"
    bm25_top_k: int = Field(default=50, ge=1)
    dense_top_k: int = Field(default=50, ge=1)
    final_top_k: int = Field(default=10, ge=1)
    fusion_method: str = "rrf"
    rerank_enabled: bool = False
    source_priority: dict[str, int] = Field(
        default_factory=lambda: {
            "standard": 5,
            "textbook": 4,
            "review": 3,
            "paper": 2,
            "webpage": 1,
        }
    )


class EmbeddingSettings(BaseModel):
    provider: str = "sentence_transformers"
    model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
    model_version: str | None = None
    batch_size: int = Field(default=32, ge=1)
    enabled: bool = True
    local_files_only: bool = True
    fallback_to_token_features: bool = True


class LlmProviderSettings(BaseModel):
    provider: str
    model: str
    api_key_env: str
    temperature: float = Field(default=0.0, ge=0.0)
    max_tokens: int = Field(default=1024, ge=1)
    timeout: float = Field(default=30.0, gt=0.0)
    reasoning_effort: str | None = None
    text_verbosity: str | None = None
    input_usd_per_million_tokens: float | None = Field(default=None, ge=0.0)
    output_usd_per_million_tokens: float | None = Field(default=None, ge=0.0)
    cached_input_usd_per_million_tokens: float | None = Field(default=None, ge=0.0)


class LlmSettings(BaseModel):
    providers: dict[str, str] = Field(default_factory=dict)
    s3_enabled: bool = False
    s4_enabled: bool = False
    s5_enabled: bool = False
    s3_timeout: float = Field(default=10.0, gt=0.0)
    replay_dir: Path = Path("tests/fixtures/llm")
    capture_enabled: bool = False
    live_enabled: bool = False
    token_budget_per_task: int = Field(default=4000, ge=1)
    token_budget_per_session: int = Field(default=30000, ge=1)
    usd_budget_per_task: float | None = Field(default=None, ge=0.0)
    openai: LlmProviderSettings = Field(
        default_factory=lambda: LlmProviderSettings(
            provider="openai",
            model="gpt-5.5",
            api_key_env="OPENAI_API_KEY",
            reasoning_effort="high",
            text_verbosity="high",
            input_usd_per_million_tokens=5.0,
            output_usd_per_million_tokens=30.0,
            cached_input_usd_per_million_tokens=0.5,
        )
    )
    anthropic: LlmProviderSettings = Field(
        default_factory=lambda: LlmProviderSettings(
            provider="anthropic",
            model="claude-opus-4-8",
            api_key_env="ANTHROPIC_API_KEY",
            max_tokens=1024,
            input_usd_per_million_tokens=5.0,
            output_usd_per_million_tokens=25.0,
            cached_input_usd_per_million_tokens=0.5,
        )
    )


class NormalizationSettings(BaseModel):
    v1_enabled: bool = True
    v1_input_enabled: bool = False
    v1_output_enabled: bool = True
    terms_path: str = "taxonomy/terms_zh_en.yaml"
    units_path: str = "taxonomy/units.yaml"


class ApiSettings(BaseModel):
    auth_enabled: bool = False
    api_key: str = ""
    cors_enabled: bool = False
    cors_allow_origins: list[str] = Field(default_factory=lambda: ["http://localhost", "http://127.0.0.1"])
    rate_limit_enabled: bool = False
    rate_limit_per_minute: int = Field(default=60, ge=1)


class Settings(BaseModel):
    app_name: str = "vibration-agent"
    log_level: str = "INFO"
    default_user_mode: UserMode = "engineering"
    phase0_pipeline: list[str] = Field(
        default_factory=lambda: [
            "s2_retrieval",
            "s3_qa_summary",
            "s4_engineering_analysis",
            "s5_formula_derivation",
            "v2_citation_check",
            "v4_style",
            "v3_reviewer",
        ]
    )
    high_risk_checks: list[str] = Field(default_factory=list)
    paths: PathSettings
    classify: ClassifySettings = Field(default_factory=ClassifySettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    ocr: OcrSettings = Field(default_factory=OcrSettings)
    chunking: ChunkingSettings = Field(default_factory=ChunkingSettings)
    retrieval: RetrievalSettings = Field(default_factory=RetrievalSettings)
    embeddings: EmbeddingSettings = Field(default_factory=EmbeddingSettings)
    routing: RoutingSettings = Field(default_factory=RoutingSettings)
    llm: LlmSettings = Field(default_factory=LlmSettings)
    normalization: NormalizationSettings = Field(default_factory=NormalizationSettings)
    api: ApiSettings = Field(default_factory=ApiSettings)


def _workspace_from(start: Path | None = None) -> Path:
    if env_workspace := os.getenv("VIBRATION_AGENT_HOME"):
        return Path(env_workspace).resolve()

    current = (start or Path.cwd()).resolve()
    for candidate in (current, *current.parents):
        if (candidate / "configs").is_dir() and (candidate / "src" / "vibration_agent").is_dir():
            return candidate
    return current


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        import yaml  # type: ignore
    except ModuleNotFoundError as exc:
        raise RuntimeError("PyYAML is required to load configs/*.yaml. Install pyyaml>=6.0.2.") from exc

    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def _merged_section(*sections: dict[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for section in sections:
        for key, value in section.items():
            if isinstance(value, dict) and isinstance(merged.get(key), dict):
                merged[key] = {**merged[key], **value}
            else:
                merged[key] = value
    return merged


def _resolve(workspace: Path, value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else (workspace / path).resolve()


def _env(name: str, default: Any) -> Any:
    value = os.getenv(name)
    return default if value is None or value == "" else value


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _optional_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    return float(value)


def _first_fallback_threshold(items: list[Any], default: float = 0.6) -> float:
    for item in items:
        if isinstance(item, dict) and "low_confidence_below" in item:
            return float(item["low_confidence_below"])
    return default


def load(workspace: Path | None = None) -> Settings:
    root = _workspace_from(workspace)
    config_dir = root / "configs"
    app_yaml = _read_yaml(config_dir / "app.yaml")
    ingestion_yaml = _read_yaml(config_dir / "ingestion.yaml")
    retrieval_yaml = _read_yaml(config_dir / "retrieval.yaml")
    embeddings_yaml = _read_yaml(config_dir / "embeddings.yaml")
    api_yaml = _read_yaml(config_dir / "api.yaml")
    llm_yaml = _read_yaml(config_dir / "llm.yaml")

    app_section = app_yaml.get("app", {})
    orchestrator_section = app_yaml.get("orchestrator", {})
    llm_section = _merged_section(app_yaml.get("llm", {}), llm_yaml.get("llm", {}))
    normalization_section = app_yaml.get("normalization", {})
    api_section = api_yaml.get("api", {})
    classify_section = ingestion_yaml.get("classify", {})
    ocr_section = ingestion_yaml.get("ocr", {})
    chunking_section = ingestion_yaml.get("chunking", {})
    routing_section = app_yaml.get("routing", {})
    retrieval_top_k = retrieval_yaml.get("top_k", {})
    retrieval_fusion = retrieval_yaml.get("fusion", {})
    rerank_section = retrieval_yaml.get("rerank", {})
    embeddings_section = embeddings_yaml.get("embeddings", {})

    data_dir = _resolve(root, _env("DATA_DIR", "data"))
    paths = PathSettings(
        workspace=root,
        data_dir=data_dir,
        raw_dir=_resolve(root, _env("RAW_DIR", data_dir / "raw")),
        ocr_dir=_resolve(root, _env("OCR_DIR", data_dir / "ocr")),
        extracted_dir=_resolve(root, _env("EXTRACTED_DIR", data_dir / "extracted")),
        chunks_dir=_resolve(root, _env("CHUNKS_DIR", data_dir / "chunks")),
        embeddings_dir=_resolve(root, _env("EMBEDDINGS_DIR", data_dir / "embeddings")),
        exports_dir=_resolve(root, _env("EXPORTS_DIR", data_dir / "exports")),
    )

    return Settings(
        app_name=str(_env("APP_NAME", app_section.get("name", "vibration-agent"))),
        log_level=str(_env("LOG_LEVEL", app_section.get("log_level", "INFO"))),
        default_user_mode=_env("DEFAULT_USER_MODE", app_section.get("default_user_mode", "engineering")),
        phase0_pipeline=list(
            orchestrator_section.get(
                "phase0_pipeline",
                [
                    "s2_retrieval",
                    "s3_qa_summary",
                    "s4_engineering_analysis",
                    "s5_formula_derivation",
                    "v2_citation_check",
                    "v4_style",
                    "v3_reviewer",
                ],
            )
        ),
        high_risk_checks=list(orchestrator_section.get("high_risk_checks", [])),
        paths=paths,
        classify=ClassifySettings(
            ocr_text_density_threshold=float(
                _env("OCR_TEXT_DENSITY_THRESHOLD", classify_section.get("ocr_text_density_threshold", 0.2))
            ),
        ),
        database=DatabaseSettings(
            postgres_url=str(_env("POSTGRES_URL", "")),
            postgres_enabled=_env_bool("POSTGRES_ENABLED", False),
            postgres_timeout=float(_env("POSTGRES_TIMEOUT", 2.0)),
            qdrant_enabled=_env_bool("QDRANT_ENABLED", False),
            qdrant_url=str(_env("QDRANT_URL", "http://localhost:6333")),
            qdrant_api_key=str(_env("QDRANT_API_KEY", "")),
            qdrant_collection=str(_env("QDRANT_COLLECTION", "chunks")),
            qdrant_vector_size=int(_env("QDRANT_VECTOR_SIZE", 384)),
            qdrant_timeout=float(_env("QDRANT_TIMEOUT", 2.0)),
            redis_url=str(_env("REDIS_URL", "redis://localhost:6379/0")),
        ),
        ocr=OcrSettings(
            primary=str(_env("OCR_PRIMARY", ocr_section.get("primary", "paddleocr"))),
            fallback=str(_env("OCR_FALLBACK", ocr_section.get("fallback", "tesseract"))),
            paddleocr_lang=str(_env("PADDLEOCR_LANG", ocr_section.get("paddleocr", {}).get("lang", "ch"))),
            tesseract_langs=str(_env("TESSERACT_LANGS", ocr_section.get("tesseract", {}).get("langs", "chi_sim+eng+osd"))),
            low_confidence_threshold=float(
                _env("OCR_LOW_CONFIDENCE_THRESHOLD", _first_fallback_threshold(ocr_section.get("fallback_triggers", [])))
            ),
            render_dpi=int(_env("OCR_RENDER_DPI", ocr_section.get("render_dpi", 220))),
        ),
        chunking=ChunkingSettings(
            target_tokens=int(_env("CHUNK_TARGET_TOKENS", chunking_section.get("target_tokens", 600))),
            overlap_tokens=int(_env("CHUNK_OVERLAP_TOKENS", chunking_section.get("overlap_tokens", 60))),
            preserve_anchors=bool(chunking_section.get("preserve_anchors", True)),
        ),
        retrieval=RetrievalSettings(
            mode=str(_env("RETRIEVAL_MODE", retrieval_yaml.get("mode", "hybrid"))),
            bm25_top_k=int(retrieval_top_k.get("bm25", 50)),
            dense_top_k=int(retrieval_top_k.get("dense", 50)),
            final_top_k=int(retrieval_top_k.get("final", 10)),
            fusion_method=str(retrieval_fusion.get("method", "rrf")),
            rerank_enabled=bool(rerank_section.get("enabled", False)),
            source_priority=dict(retrieval_yaml.get("source_priority", {})) or RetrievalSettings().source_priority,
        ),
        embeddings=EmbeddingSettings(
            provider=str(_env("EMBEDDING_PROVIDER", embeddings_section.get("provider", "sentence_transformers"))),
            model_name=str(_env("EMBEDDING_MODEL", embeddings_section.get("model_name", "sentence-transformers/all-MiniLM-L6-v2"))),
            model_version=embeddings_section.get("model_version"),
            batch_size=int(_env("EMBEDDING_BATCH_SIZE", embeddings_section.get("batch_size", 32))),
            enabled=bool(embeddings_section.get("enabled", True)),
            local_files_only=bool(embeddings_section.get("local_files_only", True)),
            fallback_to_token_features=bool(embeddings_section.get("fallback_to_token_features", True)),
        ),
        routing=RoutingSettings(
            default_owner=str(_env("ROUTING_DEFAULT_OWNER", routing_section.get("default_owner", "gpt"))),
            opus_difficulties=list(routing_section.get("opus_difficulties", ["extreme"])),
            repeated_failure_threshold=int(routing_section.get("repeated_failure_threshold", 2)),
            explicit_extreme_markers=list(routing_section.get("explicit_extreme_markers", ["extreme", "opus", "senior_supervisor"])),
        ),
        llm=LlmSettings(
            providers=dict(llm_section.get("providers", {})),
            s3_enabled=_env_bool("S3_LLM_ENABLED", bool(llm_section.get("s3_enabled", False))),
            s4_enabled=_env_bool("S4_LLM_ENABLED", bool(llm_section.get("s4_enabled", False))),
            s5_enabled=_env_bool("S5_LLM_ENABLED", bool(llm_section.get("s5_enabled", False))),
            s3_timeout=float(_env("S3_LLM_TIMEOUT", llm_section.get("s3_timeout", 10.0))),
            replay_dir=_resolve(root, _env("LLM_REPLAY_DIR", llm_section.get("replay_dir", "tests/fixtures/llm"))),
            capture_enabled=_env_bool("LLM_CAPTURE_ENABLED", bool(llm_section.get("capture_enabled", False))),
            live_enabled=_env_bool("LLM_LIVE_ENABLED", bool(llm_section.get("live_enabled", False))),
            token_budget_per_task=int(
                _env("LLM_TOKEN_BUDGET_PER_TASK", llm_section.get("token_budget_per_task", 4000))
            ),
            token_budget_per_session=int(
                _env("LLM_TOKEN_BUDGET_PER_SESSION", llm_section.get("token_budget_per_session", 30000))
            ),
            usd_budget_per_task=_optional_float(
                _env("LLM_USD_BUDGET_PER_TASK", llm_section.get("usd_budget_per_task"))
            ),
            openai=LlmProviderSettings(
                provider="openai",
                model=str(
                    _env("OPENAI_MODEL", llm_section.get("openai", {}).get("model", "gpt-5.5"))
                ),
                api_key_env=str(
                    _env("OPENAI_API_KEY_ENV", llm_section.get("openai", {}).get("api_key_env", "OPENAI_API_KEY"))
                ),
                temperature=float(
                    _env("OPENAI_TEMPERATURE", llm_section.get("openai", {}).get("temperature", 0.0))
                ),
                max_tokens=int(_env("OPENAI_MAX_TOKENS", llm_section.get("openai", {}).get("max_tokens", 1024))),
                timeout=float(_env("OPENAI_TIMEOUT", llm_section.get("openai", {}).get("timeout", 30.0))),
                reasoning_effort=str(
                    _env("OPENAI_REASONING_EFFORT", llm_section.get("openai", {}).get("reasoning_effort", "high"))
                ),
                text_verbosity=str(
                    _env("OPENAI_TEXT_VERBOSITY", llm_section.get("openai", {}).get("text_verbosity", "high"))
                ),
                input_usd_per_million_tokens=_optional_float(
                    _env(
                        "OPENAI_INPUT_USD_PER_MILLION_TOKENS",
                        llm_section.get("openai", {}).get("input_usd_per_million_tokens", 5.0),
                    )
                ),
                output_usd_per_million_tokens=_optional_float(
                    _env(
                        "OPENAI_OUTPUT_USD_PER_MILLION_TOKENS",
                        llm_section.get("openai", {}).get("output_usd_per_million_tokens", 30.0),
                    )
                ),
                cached_input_usd_per_million_tokens=_optional_float(
                    _env(
                        "OPENAI_CACHED_INPUT_USD_PER_MILLION_TOKENS",
                        llm_section.get("openai", {}).get("cached_input_usd_per_million_tokens", 0.5),
                    )
                ),
            ),
            anthropic=LlmProviderSettings(
                provider="anthropic",
                model=str(
                    _env("ANTHROPIC_MODEL", llm_section.get("anthropic", {}).get("model", "claude-opus-4-8"))
                ),
                api_key_env=str(
                    _env(
                        "ANTHROPIC_API_KEY_ENV",
                        llm_section.get("anthropic", {}).get("api_key_env", "ANTHROPIC_API_KEY"),
                    )
                ),
                temperature=float(
                    _env("ANTHROPIC_TEMPERATURE", llm_section.get("anthropic", {}).get("temperature", 0.0))
                ),
                max_tokens=int(
                    _env("ANTHROPIC_MAX_TOKENS", llm_section.get("anthropic", {}).get("max_tokens", 1024))
                ),
                timeout=float(_env("ANTHROPIC_TIMEOUT", llm_section.get("anthropic", {}).get("timeout", 30.0))),
                reasoning_effort=llm_section.get("anthropic", {}).get("reasoning_effort"),
                text_verbosity=llm_section.get("anthropic", {}).get("text_verbosity"),
                input_usd_per_million_tokens=_optional_float(
                    _env(
                        "ANTHROPIC_INPUT_USD_PER_MILLION_TOKENS",
                        llm_section.get("anthropic", {}).get("input_usd_per_million_tokens", 5.0),
                    )
                ),
                output_usd_per_million_tokens=_optional_float(
                    _env(
                        "ANTHROPIC_OUTPUT_USD_PER_MILLION_TOKENS",
                        llm_section.get("anthropic", {}).get("output_usd_per_million_tokens", 25.0),
                    )
                ),
                cached_input_usd_per_million_tokens=_optional_float(
                    _env(
                        "ANTHROPIC_CACHED_INPUT_USD_PER_MILLION_TOKENS",
                        llm_section.get("anthropic", {}).get("cached_input_usd_per_million_tokens", 0.5),
                    )
                ),
            ),
        ),
        normalization=NormalizationSettings(
            v1_enabled=_env_bool("V1_ENABLED", bool(normalization_section.get("v1_enabled", True))),
            v1_input_enabled=_env_bool(
                "V1_INPUT_ENABLED", bool(normalization_section.get("v1_input_enabled", False))
            ),
            v1_output_enabled=_env_bool(
                "V1_OUTPUT_ENABLED", bool(normalization_section.get("v1_output_enabled", True))
            ),
            terms_path=str(normalization_section.get("terms_path", "taxonomy/terms_zh_en.yaml")),
            units_path=str(normalization_section.get("units_path", "taxonomy/units.yaml")),
        ),
        api=ApiSettings(
            auth_enabled=_env_bool("API_AUTH_ENABLED", bool(api_section.get("auth_enabled", False))),
            api_key=str(_env("API_KEY", api_section.get("api_key", ""))),
            cors_enabled=_env_bool("API_CORS_ENABLED", bool(api_section.get("cors_enabled", False))),
            cors_allow_origins=list(api_section.get("cors_allow_origins", ["http://localhost", "http://127.0.0.1"])),
            rate_limit_enabled=_env_bool("API_RATE_LIMIT_ENABLED", bool(api_section.get("rate_limit_enabled", False))),
            rate_limit_per_minute=int(_env("API_RATE_LIMIT_PER_MINUTE", api_section.get("rate_limit_per_minute", 60))),
        ),
    )


__all__ = [
    "ApiSettings",
    "ClassifySettings",
    "ChunkingSettings",
    "DatabaseSettings",
    "EmbeddingSettings",
    "LlmSettings",
    "LlmProviderSettings",
    "NormalizationSettings",
    "OcrSettings",
    "PathSettings",
    "RetrievalSettings",
    "RoutingSettings",
    "Settings",
    "load",
]
