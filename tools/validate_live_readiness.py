#!/usr/bin/env python3
"""Validate SalCAPA's public live-runtime readiness contract without exposing diagnostics."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


class ReadinessContractError(ValueError):
    pass


def _require_mapping(payload: dict[str, Any], name: str) -> dict[str, Any]:
    value = payload.get(name)
    if not isinstance(value, dict):
        raise ReadinessContractError(f"{name} must be an object")
    return value


def _require_fields(value: dict[str, Any], name: str, expected: dict[str, Any]) -> None:
    for key, required in expected.items():
        if value.get(key) != required:
            raise ReadinessContractError(f"{name}.{key} did not satisfy the governed contract")


def _reject_diagnostics(value: Any) -> None:
    forbidden_keys = {"detail", "error", "errors", "exception", "traceback", "stack", "dsn", "connection_string"}
    forbidden_values = ("postgresql://", "password=", "access_token", "client_secret", "traceback")
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key).lower() in forbidden_keys:
                raise ReadinessContractError("public readiness payload contains diagnostic fields")
            _reject_diagnostics(item)
    elif isinstance(value, list):
        for item in value:
            _reject_diagnostics(item)
    elif isinstance(value, str):
        lowered = value.lower()
        if any(marker in lowered for marker in forbidden_values):
            raise ReadinessContractError("public readiness payload contains sensitive diagnostic content")


def validate(payload: Any, expected_environment: str) -> None:
    if not isinstance(payload, dict):
        raise ReadinessContractError("readiness payload must be an object")
    if payload.get("ready") is not True:
        raise ReadinessContractError("runtime is not ready")
    if payload.get("environment") != expected_environment:
        raise ReadinessContractError("runtime environment does not match the governed target")
    if payload.get("auth_mode") != "oidc":
        raise ReadinessContractError("runtime authentication is not OIDC")
    if payload.get("storage_backend") != "azure":
        raise ReadinessContractError("runtime evidence storage is not Azure Blob")
    if payload.get("issues") != []:
        raise ReadinessContractError("runtime reported readiness issues")

    _require_fields(
        _require_mapping(payload, "secret_provider"),
        "secret_provider",
        {"backend": "azure_keyvault", "configured": True},
    )
    _require_fields(
        _require_mapping(payload, "rate_limit"),
        "rate_limit",
        {"enabled": True, "healthy": True},
    )
    _require_fields(
        _require_mapping(payload, "telemetry"),
        "telemetry",
        {"backend": "azure_monitor", "healthy": True},
    )
    _require_fields(
        _require_mapping(payload, "runtime_database"),
        "runtime_database",
        {"provider": "postgresql", "configured": True, "healthy": True},
    )
    _require_fields(
        _require_mapping(payload, "managed_database_target"),
        "managed_database_target",
        {"provider": "postgresql", "target": "postgresql", "configured": True, "healthy": True},
    )
    _require_fields(
        _require_mapping(payload, "oidc"),
        "oidc",
        {"provider": "entra", "mode": "managed_identity", "configured": True, "healthy": True},
    )
    _reject_diagnostics(payload)


def accepted_fixture() -> dict[str, Any]:
    return {
        "ready": True,
        "version": "3.0.0",
        "environment": "dev",
        "auth_mode": "oidc",
        "storage_backend": "azure",
        "av_mode": "disabled",
        "secret_provider": {"backend": "azure_keyvault", "configured": True},
        "rate_limit": {"backend": "memory", "enabled": True, "healthy": True},
        "telemetry": {"backend": "azure_monitor", "healthy": True},
        "runtime_database": {"provider": "postgresql", "configured": True, "healthy": True},
        "managed_database_target": {"provider": "postgresql", "target": "postgresql", "configured": True, "healthy": True},
        "oidc": {"provider": "entra", "mode": "managed_identity", "configured": True, "healthy": True},
        "issues": [],
    }


def self_test() -> None:
    valid = accepted_fixture()
    validate(valid, "dev")
    mutations = [
        ("not-ready", lambda p: p.update(ready=False)),
        ("wrong-environment", lambda p: p.update(environment="prod")),
        ("local-storage", lambda p: p.update(storage_backend="local")),
        ("database-unhealthy", lambda p: p["runtime_database"].update(healthy=False)),
        ("oidc-secret", lambda p: p["oidc"].update(mode="client_secret")),
        ("diagnostic", lambda p: p.update(detail="postgresql://host/db")),
    ]
    for name, mutate in mutations:
        candidate = json.loads(json.dumps(valid))
        mutate(candidate)
        try:
            validate(candidate, "dev")
        except ReadinessContractError:
            continue
        raise AssertionError(f"{name} mutation was accepted")
    print("LIVE_RUNTIME_READINESS_CONTRACT_PASS")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("payload", nargs="?", type=Path)
    parser.add_argument("--environment", default="dev")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return
    if args.payload is None:
        parser.error("payload is required unless --self-test is used")
    try:
        payload = json.loads(args.payload.read_text())
        validate(payload, args.environment)
    except (OSError, json.JSONDecodeError, ReadinessContractError) as exc:
        raise SystemExit(f"Live runtime readiness rejected: {exc}") from None
    print("LIVE_RUNTIME_READINESS_ACCEPTED")


if __name__ == "__main__":
    main()
