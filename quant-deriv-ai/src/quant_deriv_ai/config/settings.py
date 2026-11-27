"""Pydantic settings and YAML config loader."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from quant_deriv_ai.core.exceptions import ConfigError, TradingModeError
from quant_deriv_ai.core.models import TradingMode


class AppSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = "quant-deriv-ai"
    environment: str = "development"
    log_level: str = "INFO"


class TradingSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: TradingMode = TradingMode.DEMO
    allow_live: bool = False

    @field_validator("mode")
    @classmethod
    def _demo_only(cls, value: TradingMode) -> TradingMode:
        return validate_trading_mode(value)

    @field_validator("allow_live")
    @classmethod
    def _forbid_live_flag(cls, value: bool) -> bool:
        if value:
            msg = "allow_live=true is forbidden in this phase (DEMO only)"
            raise TradingModeError(msg)
        return value


class RiskSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    capital_preservation_priority: bool = True
    martingale_forbidden: bool = True
    aggressive_loss_recovery_forbidden: bool = True
    require_demonstrated_edge: bool = True
    abstain_without_edge: bool = True


class Mt5Settings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    terminal_path: str = ""
    timeout_ms: int = Field(default=60_000, ge=1_000, le=600_000)
    max_retries: int = Field(default=3, ge=0, le=20)
    backoff_base_s: float = Field(default=0.5, ge=0.05, le=60.0)
    heartbeat_interval_s: float = Field(default=30.0, ge=1.0, le=600.0)


class LoggingSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    structured: bool = True
    serialize: bool = False
    sink: str = "stderr"


class QuantConfig(BaseModel):
    """Root configuration document."""

    model_config = ConfigDict(extra="forbid")

    app: AppSettings = Field(default_factory=AppSettings)
    trading: TradingSettings = Field(default_factory=TradingSettings)
    risk: RiskSettings = Field(default_factory=RiskSettings)
    mt5: Mt5Settings = Field(default_factory=Mt5Settings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)


class EnvSettings(BaseSettings):
    """Environment-backed overrides (no secrets required for LOT-001)."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    quant_env: str | None = None
    quant_log_level: str | None = None
    quant_config_path: str | None = None
    quant_trading_mode: str | None = None
    mt5_login: str | None = None
    mt5_password: str | None = None
    mt5_server: str | None = None
    mt5_path: str | None = None


def validate_trading_mode(mode: TradingMode | str) -> TradingMode:
    """Reject any non-DEMO trading mode."""
    value = TradingMode(mode) if not isinstance(mode, TradingMode) else mode
    if value is not TradingMode.DEMO:
        msg = f"trading mode {value!r} rejected — DEMO only in this phase"
        raise TradingModeError(msg)
    return value


def _default_config_path() -> Path:
    env_path = os.environ.get("QUANT_CONFIG_PATH")
    if env_path:
        return Path(env_path)
    # Prefer package-relative project config when running from repo root.
    cwd_candidate = Path.cwd() / "config" / "default.yaml"
    if cwd_candidate.is_file():
        return cwd_candidate
    # Fall back next to the installed package's project tree (dev editable).
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "config" / "default.yaml"
        if candidate.is_file():
            return candidate
    return cwd_candidate


def load_config(path: str | Path | None = None) -> QuantConfig:
    """Load and validate YAML configuration."""
    config_path = Path(path) if path else _default_config_path()
    if not config_path.is_file():
        msg = f"config file not found: {config_path}"
        raise ConfigError(msg)
    try:
        raw: Any = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        msg = f"invalid YAML in {config_path}: {exc}"
        raise ConfigError(msg) from exc
    if not isinstance(raw, dict):
        msg = f"config root must be a mapping, got {type(raw).__name__}"
        raise ConfigError(msg)

    env = EnvSettings()
    if env.quant_env:
        raw.setdefault("app", {})
        if isinstance(raw["app"], dict):
            raw["app"]["environment"] = env.quant_env
    if env.quant_log_level:
        raw.setdefault("app", {})
        if isinstance(raw["app"], dict):
            raw["app"]["log_level"] = env.quant_log_level
    if env.quant_trading_mode:
        raw.setdefault("trading", {})
        if isinstance(raw["trading"], dict):
            raw["trading"]["mode"] = env.quant_trading_mode
    if env.mt5_path:
        raw.setdefault("mt5", {})
        if isinstance(raw["mt5"], dict):
            raw["mt5"]["terminal_path"] = env.mt5_path

    try:
        return QuantConfig.model_validate(raw)
    except TradingModeError:
        raise
    except Exception as exc:  # pydantic ValidationError included
        msg = f"config validation failed for {config_path}: {exc}"
        raise ConfigError(msg) from exc
