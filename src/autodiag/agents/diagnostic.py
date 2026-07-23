"""Análise de diagnóstico com Claude (opcional — exige ANTHROPIC_API_KEY)."""
import os
from collections.abc import Callable

import anthropic

from autodiag.core.vehicle import VehicleProfile
from autodiag.elm327.reader import DTCRecord, LivePIDs

DEFAULT_MODEL = "claude-opus-4-8"

_SYSTEM = """Você é um mecânico especialista em diagnóstico eletrônico veicular (OBD2).
Analise os dados recebidos e forneça:
1. Diagnóstico provável (causa raiz)
2. Nível de urgência: CRÍTICO / ATENÇÃO / INFORMATIVO
3. Ação recomendada (o que fazer agora)
4. Estimativa de custo de reparo em BRL (se aplicável)
5. O que NÃO fazer (erros comuns)

Seja direto e objetivo. Use linguagem técnica mas acessível."""

_client: anthropic.Anthropic | None = None


class AIUnavailableError(RuntimeError):
    """A análise por IA não pôde ser executada (chave, rede ou serviço)."""


def is_configured() -> bool:
    """True quando há credencial da Anthropic disponível no ambiente."""
    return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic()  # resolve credenciais do ambiente
    return _client


def analyze(
    vehicle: VehicleProfile,
    dtcs: list[DTCRecord],
    pids: LivePIDs,
    *,
    model: str = DEFAULT_MODEL,
    on_text: Callable[[str], None] | None = None,
) -> str:
    """Gera o parecer de diagnóstico. ``on_text`` recebe o texto em streaming."""
    dtc_list = ", ".join(d.code for d in dtcs) if dtcs else "Nenhum"
    pids_text = "\n".join(f"  {k}: {v}" for k, v in pids.as_dict().items())

    prompt = f"""Veículo: {vehicle.label}
VIN: {vehicle.vin or 'não disponível'}

Códigos de falha (DTCs): {dtc_list}

PIDs ao vivo:
{pids_text or '  (não disponíveis)'}"""

    try:
        with _get_client().messages.stream(
            model=model,
            max_tokens=4096,
            thinking={"type": "adaptive"},
            system=_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            parts: list[str] = []
            for text in stream.text_stream:
                parts.append(text)
                if on_text:
                    on_text(text)
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
