from app.settings import MnemosyneSettings, parse_bool_env


def test_feature_flags_default_to_off(monkeypatch) -> None:
    monkeypatch.delenv("MNEMOSYNE_DOMAIN_POLICY_ENABLED", raising=False)
    monkeypatch.delenv("MNEMOSYNE_ACCESS_CONTEXT_HEADERS_ENABLED", raising=False)
    monkeypatch.delenv("MNEMOSYNE_SAFE_PROJECTIONS_ENABLED", raising=False)
    monkeypatch.delenv("MNEMOSYNE_ACCESS_AUDIT_ENABLED", raising=False)

    settings = MnemosyneSettings.from_env()

    assert settings.domain_policy_enabled is False
    assert settings.access_context_headers_enabled is False
    assert settings.safe_projections_enabled is False
    assert settings.access_audit_enabled is False


def test_feature_flags_parse_truthy_values(monkeypatch) -> None:
    monkeypatch.setenv("MNEMOSYNE_DOMAIN_POLICY_ENABLED", "true")
    monkeypatch.setenv("MNEMOSYNE_ACCESS_CONTEXT_HEADERS_ENABLED", "1")
    monkeypatch.setenv("MNEMOSYNE_SAFE_PROJECTIONS_ENABLED", "yes")
    monkeypatch.setenv("MNEMOSYNE_ACCESS_AUDIT_ENABLED", "on")

    settings = MnemosyneSettings.from_env()

    assert settings.domain_policy_enabled is True
    assert settings.access_context_headers_enabled is True
    assert settings.safe_projections_enabled is True
    assert settings.access_audit_enabled is True


def test_legacy_access_policy_flag_enables_domain_policy(monkeypatch) -> None:
    monkeypatch.delenv("MNEMOSYNE_DOMAIN_POLICY_ENABLED", raising=False)
    monkeypatch.setenv("MNEMOSYNE_ACCESS_POLICY_ENABLED", "true")

    settings = MnemosyneSettings.from_env()

    assert settings.domain_policy_enabled is True


def test_parse_bool_rejects_unknown_values() -> None:
    try:
        parse_bool_env("maybe", name="MNEMOSYNE_DOMAIN_POLICY_ENABLED")
    except ValueError as exc:
        assert "MNEMOSYNE_DOMAIN_POLICY_ENABLED" in str(exc)
    else:
        raise AssertionError("Expected invalid boolean value to fail")
