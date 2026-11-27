"""``quant doctor`` — environment, dependency, and MT5 prerequisite checks."""

from __future__ import annotations

import contextlib
import importlib.util
import platform
import sys
from dataclasses import dataclass
from importlib import metadata


@dataclass(frozen=True, slots=True)
class CheckResult:
    name: str
    ok: bool
    detail: str


REQUIRED_MODULES = (
    "pydantic",
    "pydantic_settings",
    "yaml",
    "dotenv",
    "typer",
    "rich",
    "loguru",
)


def _check_python() -> CheckResult:
    major, minor = sys.version_info[:2]
    ok = (major, minor) == (3, 12)
    return CheckResult(
        name="python",
        ok=ok,
        detail=f"{platform.python_version()} (required: 3.12.x) on {platform.system()}",
    )


def _check_module(module_name: str) -> CheckResult:
    spec = importlib.util.find_spec(module_name)
    if spec is None:
        return CheckResult(name=f"dep:{module_name}", ok=False, detail="not importable")
    version = "unknown"
    dist_map = {
        "yaml": "PyYAML",
        "dotenv": "python-dotenv",
        "pydantic_settings": "pydantic-settings",
    }
    dist_name = dist_map.get(module_name, module_name)
    with contextlib.suppress(metadata.PackageNotFoundError):
        version = metadata.version(dist_name)
    return CheckResult(name=f"dep:{module_name}", ok=True, detail=f"ok ({version})")


def check_mt5() -> CheckResult:
    """Attempt MetaTrader5 import. Do not invent PASS — report OS limits accurately."""
    system = platform.system()
    spec = importlib.util.find_spec("MetaTrader5")
    if spec is None:
        note = (
            f"MetaTrader5 not installed. Official wheels are Windows-oriented; "
            f"current OS={system}. Install optional extra 'mt5' on Windows only."
        )
        return CheckResult(name="mt5:import", ok=False, detail=note)
    try:
        import MetaTrader5 as mt5

        ver = getattr(mt5, "__version__", "unknown")
        return CheckResult(
            name="mt5:import",
            ok=True,
            detail=f"importable version={ver} on {system}",
        )
    except Exception as exc:  # noqa: BLE001 — doctor must report real failure
        return CheckResult(
            name="mt5:import",
            ok=False,
            detail=f"package present but import failed on {system}: {exc}",
        )


def check_mt5_prerequisites() -> list[CheckResult]:
    """MT5 prerequisites without connecting to any trading account."""
    results: list[CheckResult] = [check_mt5()]
    system = platform.system()
    if system != "Windows":
        results.append(
            CheckResult(
                name="mt5:platform",
                ok=False,
                detail=(
                    f"OS={system}: MetaTrader5 terminal + official Python package "
                    "target Windows. Linux/macOS hosts cannot run the native MT5 bridge."
                ),
            )
        )
    else:
        results.append(
            CheckResult(
                name="mt5:platform",
                ok=True,
                detail="Windows detected — MT5 terminal may be installed locally "
                "(terminal presence not probed; no account connection attempted).",
            )
        )
    results.append(
        CheckResult(
            name="mt5:account",
            ok=True,
            detail="skipped by design — doctor never connects to demo or live accounts",
        )
    )
    return results


def run_doctor() -> list[CheckResult]:
    results: list[CheckResult] = [_check_python()]
    for mod in REQUIRED_MODULES:
        results.append(_check_module(mod))
    results.extend(check_mt5_prerequisites())
    return results


def doctor_passed(results: list[CheckResult]) -> bool:
    """Overall doctor pass = Python + required deps OK. MT5 may fail on non-Windows."""
    mandatory = [r for r in results if r.name == "python" or r.name.startswith("dep:")]
    return all(r.ok for r in mandatory)
