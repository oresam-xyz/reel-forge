"""Configuration loading from config.yaml."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)


class ProviderConfig(BaseModel):
    model_config = ConfigDict(extra="allow")

    provider: str


class OutputConfig(BaseModel):
    format: str = "9x16"
    resolution: str = "1080x1920"
    target_duration_seconds: int = 60


class AppConfig(BaseModel):
    providers: dict[str, ProviderConfig] = Field(default_factory=dict)
    output: OutputConfig = Field(default_factory=OutputConfig)
    brands_dir: str = "./brands"
    projects_dir: str = "./projects"


def _resolve_env_vars(obj: Any) -> Any:
    """Recursively resolve 'env:VAR_NAME' strings to environment variable values."""
    if isinstance(obj, str) and obj.startswith("env:"):
        var_name = obj[4:]
        value = os.environ.get(var_name, "")
        if not value:
            logger.warning("Environment variable %s is not set", var_name)
        return value
    if isinstance(obj, dict):
        return {k: _resolve_env_vars(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_resolve_env_vars(v) for v in obj]
    return obj


def load_config(path: Path | None = None) -> AppConfig:
    """Load and validate configuration from a YAML file."""
    if path is None:
        path = Path("config.yaml")

    if not path.exists():
        logger.warning("Config file %s not found, using defaults", path)
        return AppConfig()

    raw = yaml.safe_load(path.read_text())
    if raw is None:
        return AppConfig()

    resolved = _resolve_env_vars(raw)
    config = AppConfig.model_validate(resolved)
    logger.info("Loaded config from %s", path)
    return config
