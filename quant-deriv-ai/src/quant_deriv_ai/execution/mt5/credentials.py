"""Secure credential loading for MT5 DEMO accounts — never log secrets."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from quant_deriv_ai.config.settings import EnvSettings
from quant_deriv_ai.core.exceptions import ConfigError
from quant_deriv_ai.security.guards import redact_secrets


@dataclass(frozen=True, slots=True)
class Mt5Credentials:
    """In-memory DEMO credentials. ``password`` must never be logged or serialized."""

    login: int
    password: str
    server: str
    terminal_path: str = ""

    def safe_dict(self) -> dict[str, str | int]:
        """Return a redacted representation safe for logs/status."""
        return redact_secrets(
            {
                "login": self.login,
                "password": self.password,
                "server": self.server,
                "terminal_path": self.terminal_path or "",
            }
        )


def load_credentials_from_env(
    *,
    require_complete: bool = True,
    env_file: str | Path | None = None,
) -> Mt5Credentials | None:
    """Load MT5 credentials from process env and optional ``.env`` file.

    Uses :class:`EnvSettings` so values from a local ``.env`` (as documented in
    the README) work without requiring shell exports. Process environment
    variables still take precedence over the file.

    Expected keys (placeholders only in ``.env.example``):
    ``MT5_LOGIN``, ``MT5_PASSWORD``, ``MT5_SERVER``, optional ``MT5_PATH``.

    Never logs credential values.
    """
    settings_kwargs: dict[str, object] = {}
    if env_file is not None:
        settings_kwargs["_env_file"] = str(env_file)
    env = EnvSettings(**settings_kwargs)  # type: ignore[arg-type]

    login_raw = (env.mt5_login or "").strip()
    password = env.mt5_password or ""
    server = (env.mt5_server or "").strip()
    path = (env.mt5_path or "").strip()

    if not login_raw and not password and not server:
        if require_complete:
            msg = (
                "MT5 credentials missing — set MT5_LOGIN, MT5_PASSWORD, MT5_SERVER "
                "in the environment or a local .env (DEMO only; never commit secrets)"
            )
            raise ConfigError(msg)
        return None

    missing = [
        name
        for name, value in (
            ("MT5_LOGIN", login_raw),
            ("MT5_PASSWORD", password),
            ("MT5_SERVER", server),
        )
        if not value
    ]
    if missing:
        msg = f"incomplete MT5 credentials — missing: {', '.join(missing)}"
        raise ConfigError(msg)

    try:
        login = int(login_raw)
    except ValueError as exc:
        msg = "MT5_LOGIN must be an integer account number"
        raise ConfigError(msg) from exc

    if login <= 0:
        msg = "MT5_LOGIN must be a positive account number"
        raise ConfigError(msg)

    return Mt5Credentials(
        login=login,
        password=password,
        server=server,
        terminal_path=path,
    )
