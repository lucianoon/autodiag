"""Porta única para LLMs — qualquer modelo, um contrato só.

Dois backends implementam a mesma função de streaming:

- ``anthropic`` — SDK nativo da Anthropic, com thinking adaptativo.
- ``openai`` — qualquer endpoint que fale a API de chat completions da OpenAI.
  Isso cobre OpenAI, OpenRouter, Groq, Together, DeepInfra, Fireworks, vLLM,
  Ollama e LM Studio sem código específico por provedor.

A escolha é toda por ambiente, então trocar de modelo não exige editar código:

===========================  ==============================================
``AUTODIAG_LLM_BACKEND``     ``auto`` (padrão), ``anthropic`` ou ``openai``
``AUTODIAG_MODEL``           id do modelo; cada backend tem um default
``AUTODIAG_BASE_URL``        endpoint OpenAI-compatible (ativa o backend
                             ``openai`` no modo ``auto``)
``AUTODIAG_API_KEY``         credencial; cai para ``OPENAI_API_KEY`` ou
                             ``ANTHROPIC_API_KEY`` conforme o backend
===========================  ==============================================

No modo ``auto`` a resolução é: chave da Anthropic ⇒ ``anthropic``; senão,
base URL ou chave OpenAI ⇒ ``openai``; senão, não configurado.

Servidores locais (Ollama, LM Studio, vLLM) normalmente não pedem credencial.
Quando há base URL e nenhuma chave, mandamos um placeholder — o cliente da
OpenAI exige uma string não vazia, o servidor local ignora o valor.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass

DEFAULT_ANTHROPIC_MODEL = "claude-opus-5"
DEFAULT_OPENAI_MODEL = "gpt-4.1-mini"

#: Enviado quando há base URL mas nenhuma credencial (servidores locais).
LOCAL_PLACEHOLDER_KEY = "not-needed"


class AIUnavailableError(RuntimeError):
    """A análise por IA não pôde ser executada (chave, rede ou serviço)."""


@dataclass(frozen=True)
class ProviderConfig:
    """Backend, modelo e credenciais já resolvidos a partir do ambiente."""

    backend: str
    model: str
    api_key: str | None = None
    base_url: str | None = None


def _env(*names: str) -> str | None:
    """Primeiro valor não vazio entre as variáveis informadas."""
    for name in names:
        value = os.environ.get(name)
        if value:
            return value
    return None


def _anthropic_key() -> str | None:
    return _env("AUTODIAG_API_KEY", "ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")


def _openai_key() -> str | None:
    return _env("AUTODIAG_API_KEY", "OPENAI_API_KEY")


def _base_url() -> str | None:
    return _env("AUTODIAG_BASE_URL", "OPENAI_BASE_URL")


def resolve_backend() -> str | None:
    """Backend efetivo, ou ``None`` quando nada está configurado.

    Um backend pedido explicitamente é respeitado mesmo sem credencial: quem
    define ``AUTODIAG_LLM_BACKEND`` quer um erro claro, não um fallback mudo.
    """
    requested = (os.environ.get("AUTODIAG_LLM_BACKEND") or "auto").strip().lower()
    if requested in {"anthropic", "openai"}:
        return requested
    if requested not in {"auto", ""}:
        raise AIUnavailableError(
            f"AUTODIAG_LLM_BACKEND inválido: {requested!r}. "
            "Use 'auto', 'anthropic' ou 'openai'."
        )
    if _anthropic_key():
        return "anthropic"
    if _base_url() or _openai_key():
        return "openai"
    return None


def resolve(model: str | None = None) -> ProviderConfig:
    """Monta a configuração do provider. ``model`` sobrescreve o ambiente."""
    backend = resolve_backend()
    if backend is None:
        raise AIUnavailableError(
            "Nenhum modelo configurado. Defina ANTHROPIC_API_KEY, OPENAI_API_KEY "
            "ou AUTODIAG_BASE_URL (para um servidor local como Ollama)."
        )
    chosen = model or os.environ.get("AUTODIAG_MODEL") or None
    if backend == "anthropic":
        return ProviderConfig(
            backend="anthropic",
            model=chosen or DEFAULT_ANTHROPIC_MODEL,
            api_key=_anthropic_key(),
        )
    base_url = _base_url()
    return ProviderConfig(
        backend="openai",
        model=chosen or DEFAULT_OPENAI_MODEL,
        api_key=_openai_key() or (LOCAL_PLACEHOLDER_KEY if base_url else None),
        base_url=base_url,
    )


def is_configured() -> bool:
    """True quando algum backend consegue ser resolvido a partir do ambiente."""
    try:
        return resolve_backend() is not None
    except AIUnavailableError:
        return False


def describe() -> str:
    """Rótulo curto do backend ativo, para exibir na CLI e na web."""
    try:
        config = resolve()
    except AIUnavailableError:
        return "não configurado"
    if config.base_url:
        return f"{config.model} @ {config.base_url}"
    return config.model


def _stream_anthropic(
    config: ProviderConfig,
    system: str,
    prompt: str,
    on_text: Callable[[str], None] | None,
    max_tokens: int,
) -> str:
    import anthropic

    # Sem chave explícita, o SDK resolve credenciais do ambiente sozinho.
    client = (
        anthropic.Anthropic(api_key=config.api_key)
        if config.api_key
        else anthropic.Anthropic()
    )
    try:
        with client.messages.stream(
            model=config.model,
            max_tokens=max_tokens,
            thinking={"type": "adaptive"},
            system=system,
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            parts: list[str] = []
            for text in stream.text_stream:
                parts.append(text)
                if on_text:
                    on_text(text)
            # Os classificadores de segurança podem recusar a requisição: a
            # resposta é HTTP 200 com stop_reason="refusal" e conteúdo vazio ou
            # parcial. Sem esta checagem o parecer sairia truncado em silêncio.
            if stream.get_final_message().stop_reason == "refusal":
                raise AIUnavailableError(
                    "O modelo recusou a análise por política de conteúdo. "
                    "Rode com --no-ai ou aponte AUTODIAG_MODEL para outro modelo."
                )
            return "".join(parts)
    except anthropic.AuthenticationError as e:
        raise AIUnavailableError(
            "Credencial da Anthropic inválida. Verifique ANTHROPIC_API_KEY."
        ) from e
    except anthropic.RateLimitError as e:
        raise AIUnavailableError(
            "Limite de requisições da API atingido. Tente novamente em instantes."
        ) from e
    except anthropic.APIConnectionError as e:
        raise AIUnavailableError(
            "Sem conexão com a API da Anthropic. Verifique sua rede."
        ) from e
    except anthropic.APIStatusError as e:
        raise AIUnavailableError(f"Erro da API da Anthropic ({e.status_code}).") from e


def _stream_openai(
    config: ProviderConfig,
    system: str,
    prompt: str,
    on_text: Callable[[str], None] | None,
    max_tokens: int,
) -> str:
    try:
        import openai
    except ImportError as e:  # pragma: no cover - depende do ambiente
        raise AIUnavailableError(
            "Backend OpenAI-compatible exige o pacote 'openai'. "
            "Instale com: pip install 'autodiag[openai]'"
        ) from e

    client = openai.OpenAI(api_key=config.api_key, base_url=config.base_url)
    try:
        stream = client.chat.completions.create(
            model=config.model,
            max_tokens=max_tokens,
            stream=True,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
        )
        parts: list[str] = []
        for chunk in stream:
            if not chunk.choices:
                continue
            text = chunk.choices[0].delta.content
            if not text:
                continue
            parts.append(text)
            if on_text:
                on_text(text)
        return "".join(parts)
    except openai.AuthenticationError as e:
        raise AIUnavailableError(
            "Credencial inválida para o endpoint OpenAI-compatible. "
            "Verifique AUTODIAG_API_KEY ou OPENAI_API_KEY."
        ) from e
    except openai.RateLimitError as e:
        raise AIUnavailableError(
            "Limite de requisições atingido. Tente novamente em instantes."
        ) from e
    except openai.APIConnectionError as e:
        target = config.base_url or "api.openai.com"
        raise AIUnavailableError(f"Sem conexão com {target}. Verifique sua rede.") from e
    except openai.APIStatusError as e:
        raise AIUnavailableError(
            f"Erro do endpoint OpenAI-compatible ({e.status_code})."
        ) from e


def stream_text(
    system: str,
    prompt: str,
    *,
    model: str | None = None,
    on_text: Callable[[str], None] | None = None,
    max_tokens: int = 4096,
) -> str:
    """Gera texto pelo backend configurado. ``on_text`` recebe o streaming."""
    config = resolve(model)
    if config.backend == "anthropic":
        return _stream_anthropic(config, system, prompt, on_text, max_tokens)
    return _stream_openai(config, system, prompt, on_text, max_tokens)
