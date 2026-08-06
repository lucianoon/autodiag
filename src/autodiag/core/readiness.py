"""
Prontidão dos monitores OBD2 e detecção de limpeza recente de DTCs.

Quando alguém apaga os códigos de falha (modo 04), os monitores de
prontidão voltam a "incompleto" e os contadores de ciclos de aquecimento
(PID 30) e distância desde a limpeza (PID 31) zeram. Um veículo à venda
com zero DTCs, monitores incompletos e pouca distância desde a limpeza é
o quadro clássico de scan apagado antes de uma vistoria — a fraude mais
comum na venda de seminovos.

Este módulo transforma esses sinais em um veredicto estruturado e
auditável para o laudo.
"""
from dataclasses import dataclass, field
from typing import Any

from autodiag.elm327.reader import MonitorStatus

# Limiares do quadro de limpeza recente. Um ciclo completo de condução
# (drive cycle) exige em geral bem mais que isso para fechar os monitores.
_DISTANCE_SUSPICION_KM = 100
_WARMUPS_SUSPICION = 10
_MIN_INCOMPLETE_FOR_SUSPICION = 2

VERDICT_SUSPEITO = "suspeito"
VERDICT_NORMAL = "normal"
VERDICT_INCONCLUSIVO = "inconclusivo"


@dataclass
class ClearAssessment:
    """Veredicto sobre limpeza recente de DTCs, com evidências auditáveis."""

    verdict: str  # suspeito | normal | inconclusivo
    confidence: str  # alta | media | baixa
    evidence: list[str] = field(default_factory=list)
    recommendation: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict,
            "confidence": self.confidence,
            "evidence": list(self.evidence),
            "recommendation": self.recommendation,
        }


def assess_recent_clear(
    status: MonitorStatus,
    warmups_since_clear: int | None = None,
    distance_since_clear_km: int | None = None,
) -> ClearAssessment:
    """Avalia se os DTCs foram apagados recentemente (quadro de vistoria)."""
    monitors = status.monitors or {}
    if not monitors:
        return ClearAssessment(
            verdict=VERDICT_INCONCLUSIVO,
            confidence="baixa",
            evidence=["Veículo não reportou o estado dos monitores de prontidão"],
            recommendation="Repita a leitura com o motor em funcionamento ou em outro protocolo.",
        )

    incomplete = [name for name, done in monitors.items() if not done]
    dtc_count = status.dtc_count or 0
    evidence: list[str] = []

    if incomplete:
        evidence.append(
            f"{len(incomplete)} de {len(monitors)} monitores incompletos: "
            + ", ".join(incomplete)
        )
    if distance_since_clear_km is not None:
        evidence.append(f"Distância desde a última limpeza de DTCs: {distance_since_clear_km} km")
    if warmups_since_clear is not None:
        evidence.append(f"Ciclos de aquecimento desde a limpeza: {warmups_since_clear}")

    base_suspicion = dtc_count == 0 and len(incomplete) >= _MIN_INCOMPLETE_FOR_SUSPICION
    strong_signal = (
        distance_since_clear_km is not None
        and distance_since_clear_km < _DISTANCE_SUSPICION_KM
    ) or (warmups_since_clear is not None and warmups_since_clear < _WARMUPS_SUSPICION)

    if base_suspicion and strong_signal:
        evidence.insert(0, "Zero DTCs com monitores incompletos e pouca rodagem desde a limpeza")
        return ClearAssessment(
            verdict=VERDICT_SUSPEITO,
            confidence="alta",
            evidence=evidence,
            recommendation=(
                "Quadro típico de códigos apagados pouco antes da inspeção. "
                "Rode 100+ km com ciclos completos de condução e repita o scan "
                "antes de fechar negócio ou emitir laudo."
            ),
        )
    if base_suspicion:
        evidence.insert(0, "Zero DTCs com monitores incompletos")
        return ClearAssessment(
            verdict=VERDICT_SUSPEITO,
            confidence="media",
            evidence=evidence,
            recommendation=(
                "Monitores incompletos sem nenhum DTC sugerem limpeza recente. "
                "Repita o scan após alguns dias de uso normal do veículo."
            ),
        )
    if incomplete and dtc_count > 0:
        return ClearAssessment(
            verdict=VERDICT_NORMAL,
            confidence="media",
            evidence=evidence,
            recommendation=(
                "Há DTCs presentes: as falhas já retornaram após a última limpeza. "
                "Diagnostique os códigos lidos."
            ),
        )
    return ClearAssessment(
        verdict=VERDICT_NORMAL,
        confidence="alta",
        evidence=evidence or ["Todos os monitores suportados estão completos"],
        recommendation="Sem indício de limpeza recente de códigos.",
    )


def build_readiness_summary(
    status: MonitorStatus,
    warmups_since_clear: int | None = None,
    distance_since_clear_km: int | None = None,
) -> dict[str, Any]:
    """Estrutura persistível (histórico/laudo) com monitores e veredicto."""
    assessment = assess_recent_clear(status, warmups_since_clear, distance_since_clear_km)
    summary: dict[str, Any] = {
        "monitors": dict(status.monitors or {}),
        "incomplete": status.incomplete_monitors,
        "clear_assessment": assessment.as_dict(),
    }
    if status.ignition is not None:
        summary["ignition"] = status.ignition
    if warmups_since_clear is not None:
        summary["warmups_since_clear"] = warmups_since_clear
    if distance_since_clear_km is not None:
        summary["distance_since_clear_km"] = distance_since_clear_km
    return summary
