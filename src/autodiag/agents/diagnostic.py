"""Análise de diagnóstico por IA (opcional — exige um modelo configurado).

O acesso ao modelo fica todo em :mod:`autodiag.agents.provider`, que fala tanto
com a API da Anthropic quanto com qualquer endpoint OpenAI-compatible. Este
módulo monta apenas o prompt do domínio automotivo.
"""

from collections.abc import Callable

from autodiag.agents.provider import (
    AIUnavailableError,
    describe,
    is_configured,
    stream_text,
)
from autodiag.core.vehicle import VehicleProfile
from autodiag.elm327.reader import DTCRecord, LivePIDs

__all__ = ["AIUnavailableError", "analyze", "describe", "is_configured"]

_SYSTEM = """Você é um mecânico especialista em diagnóstico eletrônico veicular (OBD2).
Analise os dados recebidos e forneça:
1. Diagnóstico provável (causa raiz)
2. Nível de urgência: CRÍTICO / ATENÇÃO / INFORMATIVO
3. Ação recomendada (o que fazer agora)
4. Estimativa de custo de reparo em BRL (se aplicável)
5. O que NÃO fazer (erros comuns)

Seja direto e objetivo. Use linguagem técnica mas acessível."""


def analyze(
    vehicle: VehicleProfile,
    dtcs: list[DTCRecord],
    pids: LivePIDs,
    *,
    model: str | None = None,
    on_text: Callable[[str], None] | None = None,
) -> str:
    """Gera o parecer de diagnóstico. ``on_text`` recebe o texto em streaming.

    ``model`` sobrescreve ``AUTODIAG_MODEL``; ``None`` usa o default do backend.
    """
    dtc_list = ", ".join(d.code for d in dtcs) if dtcs else "Nenhum"
    pids_text = "\n".join(f"  {k}: {v}" for k, v in pids.as_dict().items())

    prompt = f"""Veículo: {vehicle.label}
VIN: {vehicle.vin or 'não disponível'}

Códigos de falha (DTCs): {dtc_list}

PIDs ao vivo:
{pids_text or '  (não disponíveis)'}"""

    return stream_text(_SYSTEM, prompt, model=model, on_text=on_text)
