import os
from dataclasses import dataclass


def parse_bool_env(value: str | None, *, name: str) -> bool:
    if value is None or not value.strip():
        return False
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    msg = f"{name} must be a boolean value, got {value!r}."
    raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class MnemosyneSettings:
    domain_policy_enabled: bool = False
    access_context_headers_enabled: bool = False
    safe_projections_enabled: bool = False
    access_audit_enabled: bool = False

    @classmethod
    def from_env(cls) -> "MnemosyneSettings":
        return cls(
            domain_policy_enabled=parse_bool_env(
                os.getenv("MNEMOSYNE_DOMAIN_POLICY_ENABLED"),
                name="MNEMOSYNE_DOMAIN_POLICY_ENABLED",
            ),
            access_context_headers_enabled=parse_bool_env(
                os.getenv("MNEMOSYNE_ACCESS_CONTEXT_HEADERS_ENABLED"),
                name="MNEMOSYNE_ACCESS_CONTEXT_HEADERS_ENABLED",
            ),
            safe_projections_enabled=parse_bool_env(
                os.getenv("MNEMOSYNE_SAFE_PROJECTIONS_ENABLED"),
                name="MNEMOSYNE_SAFE_PROJECTIONS_ENABLED",
            ),
            access_audit_enabled=parse_bool_env(
                os.getenv("MNEMOSYNE_ACCESS_AUDIT_ENABLED"),
                name="MNEMOSYNE_ACCESS_AUDIT_ENABLED",
            ),
        )


__all__ = ["MnemosyneSettings", "parse_bool_env"]
