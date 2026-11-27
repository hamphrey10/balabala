"""Allow ``python -m quant_deriv_ai`` to invoke the CLI."""

from __future__ import annotations

from quant_deriv_ai.cli.app import app

if __name__ == "__main__":
    app()
