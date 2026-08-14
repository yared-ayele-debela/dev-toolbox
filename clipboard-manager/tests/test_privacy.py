"""Unit tests for privacy, entropy calculation, and secret detection."""

import pytest
from clipmgr.detector.privacy import (
    calculate_shannon_entropy,
    detect_sensitive_content,
    is_password_manager_app,
    is_random_secret_string,
    mask_sensitive,
)


class TestEntropyCalculation:
    """Test Shannon entropy mathematics."""

    def test_empty_string_entropy(self) -> None:
        assert calculate_shannon_entropy("") == 0.0

    def test_low_entropy_repetitive(self) -> None:
        # A single repeated character has 0 entropy
        assert calculate_shannon_entropy("aaaaaaaaaaaaaaaaaaaa") == 0.0

    def test_natural_language_entropy(self) -> None:
        # English sentences generally have entropy around 3.0 - 4.5
        entropy = calculate_shannon_entropy("The quick brown fox jumps over the lazy dog.")
        assert 2.5 <= entropy <= 4.6
        # Repetitive natural text has lower entropy
        repetitive_entropy = calculate_shannon_entropy("hello world hello world hello world")
        assert 2.0 <= repetitive_entropy <= 3.5

    def test_high_entropy_random_secret(self) -> None:
        # Cryptographic high-entropy random key has high entropy > 4.5
        entropy = calculate_shannon_entropy("9z#K2$vP9@xL1!mQ8*wR5&bT7^cN3~jY")
        assert entropy > 4.5


class TestSecretPatterns:
    """Test regex pattern matching for well-known secrets and tokens."""

    def test_aws_access_key(self) -> None:
        sample = "export AWS_ACCESS_KEY_ID=" + "AKI" + "AIOSFODNN7EXAMPLE"
        is_sensitive, reason = detect_sensitive_content(sample)
        assert is_sensitive is True
        assert "AWS Access Key" in (reason or "")

    def test_github_pat(self) -> None:
        sample = "gh" + "p_1234567890abcdefghijklmnopqrstuvwxyzAB"
        is_sensitive, reason = detect_sensitive_content(sample)
        assert is_sensitive is True
        assert "GitHub Token" in (reason or "")

    def test_slack_token(self) -> None:
        sample = "xo" + "xb-123456789012-1234567890123-4x0mpl3t0k3n5l4ck"
        is_sensitive, reason = detect_sensitive_content(sample)
        assert is_sensitive is True
        assert "Slack Token" in (reason or "")

    def test_stripe_secret_key(self) -> None:
        sample = "sk" + "_live_51A2B3C4D5E6F7G8H9I0J1K2L3M4N5O"
        is_sensitive, reason = detect_sensitive_content(sample)
        assert is_sensitive is True
        assert "Stripe Key" in (reason or "")

    def test_private_key_pem(self) -> None:
        sample = f"-----{'BEGIN'} RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA0...\n-----{'END'} RSA PRIVATE KEY-----"
        is_sensitive, reason = detect_sensitive_content(sample)
        assert is_sensitive is True
        assert "Private Key" in (reason or "")

    def test_jwt_token(self) -> None:
        sample = "ey" + "JhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozG4mB_8A7bF5L5D9X3W2Q1E0R"
        is_sensitive, reason = detect_sensitive_content(sample)
        assert is_sensitive is True
        assert "JSON Web Token" in (reason or "")

    def test_generic_high_entropy_password(self) -> None:
        sample = "K9#mQ2$xP8*vL1@wZ"
        assert is_random_secret_string(sample) is True
        is_sensitive, reason = detect_sensitive_content(sample)
        assert is_sensitive is True

    def test_normal_text_not_sensitive(self) -> None:
        sample = "Hey, let's deploy the new website release on Friday afternoon."
        is_sensitive, _ = detect_sensitive_content(sample)
        assert is_sensitive is False


class TestPasswordManagerSourceApps:
    """Test source application inspection."""

    @pytest.mark.parametrize(
        "app_title",
        [
            "Bitwarden - Vault",
            "1Password - Password Manager",
            "KeePassXC - Passwords.kdbx",
            "LastPass Vault",
            "org.gnome.Seahorse",
            "Dashlane",
        ],
    )
    def test_password_manager_detection(self, app_title: str) -> None:
        assert is_password_manager_app(app_title) is True
        # Even innocuous text copied from a password manager should be flagged
        is_sensitive, reason = detect_sensitive_content("MySecretP@ssw0rd!", source_app=app_title)
        assert is_sensitive is True
        assert "password manager" in (reason or "").lower()

    def test_regular_app_not_password_manager(self) -> None:
        assert is_password_manager_app("Visual Studio Code") is False
        assert is_password_manager_app("Google Chrome") is False
        assert is_password_manager_app("Terminal") is False


class TestMasking:
    """Test sensitive text masking for UI previews."""

    def test_mask_sensitive(self) -> None:
        masked = mask_sensitive("super_secret_token_12345")
        assert "super_secret_token_12345" not in masked
        assert "••••" in masked
        assert "Hidden" in masked
