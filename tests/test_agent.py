"""Testes da resolução de provider e da análise IA — sem chamadas de rede."""
import pytest

from autodiag.agents import diagnostic, provider

_LLM_ENV = (
    "AUTODIAG_LLM_BACKEND",
    "AUTODIAG_MODEL",
    "AUTODIAG_BASE_URL",
    "AUTODIAG_API_KEY",
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_AUTH_TOKEN",
    "OPENAI_API_KEY",
    "OPENAI_BASE_URL",
)


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    """Isola cada teste do ambiente real — senão uma chave exportada na
    máquina de quem roda a suíte muda o backend resolvido."""
    for name in _LLM_ENV:
        monkeypatch.delenv(name, raising=False)


class TestIsConfigured:
    def test_false_without_credentials(self):
        assert provider.is_configured() is False
        assert diagnostic.is_configured() is False

    def test_true_with_anthropic_api_key(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
        assert provider.is_configured() is True

    def test_true_with_anthropic_auth_token(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "token-test")
        assert provider.is_configured() is True

    def test_true_with_openai_api_key(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-openai")
        assert provider.is_configured() is True

    def test_true_with_base_url_only(self, monkeypatch):
        """Servidor local (Ollama, LM Studio) não exige credencial."""
        monkeypatch.setenv("AUTODIAG_BASE_URL", "http://localhost:11434/v1")
        assert provider.is_configured() is True


class TestResolveBackend:
    def test_none_when_unconfigured(self):
        assert provider.resolve_backend() is None

    def test_anthropic_key_wins_in_auto(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant")
        monkeypatch.setenv("OPENAI_API_KEY", "sk-openai")
        assert provider.resolve_backend() == "anthropic"

    def test_openai_when_only_openai_key(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-openai")
        assert provider.resolve_backend() == "openai"

    def test_explicit_backend_overrides_auto(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant")
        monkeypatch.setenv("AUTODIAG_LLM_BACKEND", "openai")
        assert provider.resolve_backend() == "openai"

    def test_explicit_backend_is_case_insensitive(self, monkeypatch):
        monkeypatch.setenv("AUTODIAG_LLM_BACKEND", "  Anthropic  ")
        assert provider.resolve_backend() == "anthropic"

    def test_invalid_backend_raises(self, monkeypatch):
        monkeypatch.setenv("AUTODIAG_LLM_BACKEND", "gemini")
        with pytest.raises(provider.AIUnavailableError, match="inválido"):
            provider.resolve_backend()

    def test_is_configured_swallows_invalid_backend(self, monkeypatch):
        monkeypatch.setenv("AUTODIAG_LLM_BACKEND", "gemini")
        assert provider.is_configured() is False


class TestResolve:
    def test_raises_when_unconfigured(self):
        with pytest.raises(provider.AIUnavailableError, match="Nenhum modelo"):
            provider.resolve()

    def test_anthropic_defaults(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant")
        config = provider.resolve()
        assert config.backend == "anthropic"
        assert config.model == provider.DEFAULT_ANTHROPIC_MODEL
        assert config.base_url is None

    def test_openai_defaults(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-openai")
        config = provider.resolve()
        assert config.backend == "openai"
        assert config.model == provider.DEFAULT_OPENAI_MODEL

    def test_env_model_overrides_default(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant")
        monkeypatch.setenv("AUTODIAG_MODEL", "claude-sonnet-5")
        assert provider.resolve().model == "claude-sonnet-5"

    def test_argument_overrides_env(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant")
        monkeypatch.setenv("AUTODIAG_MODEL", "claude-sonnet-5")
        assert provider.resolve("claude-opus-5").model == "claude-opus-5"

    def test_local_server_gets_placeholder_key(self, monkeypatch):
        """O cliente da OpenAI exige string não vazia; o servidor local ignora."""
        monkeypatch.setenv("AUTODIAG_BASE_URL", "http://localhost:11434/v1")
        config = provider.resolve()
        assert config.backend == "openai"
        assert config.api_key == provider.LOCAL_PLACEHOLDER_KEY
        assert config.base_url == "http://localhost:11434/v1"

    def test_explicit_key_beats_placeholder(self, monkeypatch):
        monkeypatch.setenv("AUTODIAG_BASE_URL", "https://openrouter.ai/api/v1")
        monkeypatch.setenv("AUTODIAG_API_KEY", "sk-or-v1-real")
        assert provider.resolve().api_key == "sk-or-v1-real"

    def test_openai_base_url_is_honored(self, monkeypatch):
        monkeypatch.setenv("OPENAI_BASE_URL", "https://api.groq.com/openai/v1")
        assert provider.resolve().base_url == "https://api.groq.com/openai/v1"


class TestDescribe:
    def test_unconfigured(self):
        assert provider.describe() == "não configurado"

    def test_names_the_model(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant")
        assert provider.describe() == provider.DEFAULT_ANTHROPIC_MODEL

    def test_includes_base_url_when_present(self, monkeypatch):
        monkeypatch.setenv("AUTODIAG_BASE_URL", "http://localhost:11434/v1")
        monkeypatch.setenv("AUTODIAG_MODEL", "llama3.1")
        assert provider.describe() == "llama3.1 @ http://localhost:11434/v1"


class TestErrors:
    def test_ai_unavailable_is_runtime_error(self):
        assert issubclass(provider.AIUnavailableError, RuntimeError)

    def test_diagnostic_reexports_the_same_class(self):
        assert diagnostic.AIUnavailableError is provider.AIUnavailableError

    def test_stream_text_raises_when_unconfigured(self):
        with pytest.raises(provider.AIUnavailableError):
            provider.stream_text("system", "prompt")
