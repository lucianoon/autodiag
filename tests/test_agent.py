"""Testes do módulo de análise IA — sem chamadas de rede."""
from autodiag.agents import diagnostic


class TestIsConfigured:
    def test_false_without_credentials(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
        assert diagnostic.is_configured() is False

    def test_true_with_api_key(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
        assert diagnostic.is_configured() is True

    def test_true_with_auth_token(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "token-test")
        assert diagnostic.is_configured() is True


class TestErrors:
    def test_ai_unavailable_is_runtime_error(self):
        assert issubclass(diagnostic.AIUnavailableError, RuntimeError)
