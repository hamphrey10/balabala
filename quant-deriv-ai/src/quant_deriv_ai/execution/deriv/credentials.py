"""Secure credential loading for Deriv API — never log tokens."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from quant_deriv_ai.config.settings import EnvSettings
from quant_deriv_ai.core.exceptions import ConfigError
from quant_deriv_ai.execution.deriv.constants import DEFAULT_DERIV_ENDPOINT
from quant_deriv_ai.security.guards import redact_secrets


@dataclass(frozen=True, slots=True)
class DerivCredentials:
    """In-memory Deriv API credentials. ``api_token`` must never be logged."""

    app_id: str
    api_token: str
    endpoint: str = DEFAULT_DERIV_ENDPOINT

    def safe_dict(self) -> dict[str, str]:
        """Return a redacted representation safe for logs/status."""
        return redact_secrets(
            {
                "app_id": self.app_id,
                "api_token": self.api_token,
                "endpoint": self.endpoint,
            }
        )

    def websocket_url(self) -> str:
        """Build the official WebSocket URL with ``app_id`` query param."""
        base = self.endpoint.rstrip("/")
        sep = "&" if "?" in base else "?"
        return f"{base}{sep}app_id={self.app_id}"


def load_credentials_from_env(
    *,
    require_complete: bool = True,
    env_file: str | Path | None = None,
) -> DerivCredentials | None:
    """Load Deriv credentials from process env and optional ``.env`` file.

    Expected keys (placeholders only in ``.env.example``):
    ``DERIV_APP_ID``, ``DERIV_API_TOKEN``, optional ``DERIV_ENDPOINT``.

    Obtain access at https://api.deriv.com (register an app → app_id) and create
    an API token in the Deriv account (demo/virtual recommended). Never commit
    secrets; never log tokens.
    """
    settings_kwargs: dict[str, object] = {}
    if env_file is not None:
        settings_kwargs["_env_file"] = str(env_file)
    env = EnvSettings(**settings_kwargs)  # type: ignore[arg-type]

    app_id = (env.deriv_app_id or "").strip()
    api_token = (env.deriv_api_token or "").strip()
    endpoint = (env.deriv_endpoint or "").strip() or DEFAULT_DERIV_ENDPOINT

    if not app_id and not api_token:
        if require_complete:
            msg = (
                "Deriv credentials missing — set DERIV_APP_ID and DERIV_API_TOKEN "
                "in the environment or a local .env (DEMO only; never commit secrets). "
                "Register an app at https://api.deriv.com"
            )
            raise ConfigError(msg)
        return None

    missing = [
        name
        for name, value in (
            ("DERIV_APP_ID", app_id),
            ("DERIV_API_TOKEN", api_token),
        )
        if not value
    ]
    if missing:
        msg = f"incomplete Deriv credentials — missing: {', '.join(missing)}"
        raise ConfigError(msg)

    return DerivCredentials(app_id=app_id, api_token=api_token, endpoint=endpoint)
