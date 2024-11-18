import os
from anthropic import Anthropic
from autodiag.core.vehicle import VehicleProfile
from autodiag.elm327.reader import LivePIDs, DTCRecord

_client: Anthropic | None = None


def _get_client() -> Anthropic:
    global _client
    if _client is None:
        _client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    return _client


def analyze(
    vehicle: VehicleProfile,
    dtcs: list[DTCRecord],
    pids: LivePIDs,
    *,
    model: str = "claude-sonnet-4-6",
) -> str:
    dtc_list = ", ".join(d.code for d in dtcs) if dtcs else "Nenhum"
    pids_text = "\n".join(f"  {k}: {v}" for k, v in pids.as_dict().items())

    prompt = f"""Você é um mecânico especialista em diagnóstico eletrônico veicular (OBD2).
Analise os dados abaixo e forneça:
1. Diagnóstico provável (causa raiz)
2. Nível de urgência: CRÍTICO / ATENÇÃO / INFORMATIVO
3. Ação recomendada (o que fazer agora)
4. Estimativa de custo de reparo em BRL (se aplicável)
5. O que NÃO fazer (erros comuns)

Seja direto e objetivo. Use linguagem técnica mas acessível.

Veículo: {vehicle.label}
VIN: {vehicle.vin or 'não disponível'}

Códigos de falha (DTCs): {dtc_list}

PIDs ao vivo:
{pids_text or '  (não disponíveis)'}
"""

    response = _get_client().messages.create(
        model=model,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text
