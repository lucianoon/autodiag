"""
Parecer padronizado de vistoria a partir de uma sessão de diagnóstico.

Consolida urgência, DTCs e a verificação de limpeza recente de códigos em
um veredicto único de quatro níveis, pensado para o laudo de avaliação de
seminovos: quem lê o laudo precisa de uma resposta direta ("compra, compra
com ressalvas, re-inspeciona ou reprova"), não de uma lista de códigos.
"""
from dataclasses import dataclass, field
from typing import Any

APROVADO = "aprovado"
APROVADO_COM_RESSALVAS = "aprovado_com_ressalvas"
REINSPECIONAR = "reinspecionar"
REPROVADO = "reprovado"

LABELS = {
    APROVADO: "Aprovado",
    APROVADO_COM_RESSALVAS: "Aprovado com ressalvas",
    REINSPECIONAR: "Reinspeção necessária",
    REPROVADO: "Reprovado",
}


@dataclass
class InspectionVerdict:
    verdict: str
    label: str
    reasons: list[str] = field(default_factory=list)
    recommendation: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict,
            "label": self.label,
            "reasons": list(self.reasons),
            "recommendation": self.recommendation,
        }


def build_inspection_verdict(session: dict) -> InspectionVerdict:
    """Parecer de vistoria a partir do dicionário de sessão do histórico."""
    urgency = session.get("urgency") or "informativo"
    dtc_codes = session.get("dtc_codes") or []
    readiness = session.get("readiness") or {}
    assessment = readiness.get("clear_assessment") or {}
    clear_verdict = assessment.get("verdict")

    reasons: list[str] = []

    if urgency == "critico":
        reasons.append(
            f"Urgência crítica com {len(dtc_codes)} DTC(s): " + ", ".join(dtc_codes[:6])
        )
        return InspectionVerdict(
            verdict=REPROVADO,
            label=LABELS[REPROVADO],
            reasons=reasons,
            recommendation=(
                "Há falha classificada como crítica. Repare e re-inspecione antes "
                "de qualquer negociação ou uso prolongado do veículo."
            ),
        )

    if clear_verdict == "suspeito":
        confidence = assessment.get("confidence", "media")
        reasons.append(f"Indício de limpeza recente de códigos (confiança {confidence})")
        reasons.extend(assessment.get("evidence", [])[:3])
        return InspectionVerdict(
            verdict=REINSPECIONAR,
            label=LABELS[REINSPECIONAR],
            reasons=reasons,
            recommendation=(
                "O estado real do veículo não pode ser atestado: os monitores "
                "indicam limpeza recente de códigos. Rode 100+ km com ciclos "
                "completos de condução e repita o scan antes de emitir parecer."
            ),
        )

    if urgency == "atencao" or dtc_codes:
        if dtc_codes:
            reasons.append(f"{len(dtc_codes)} DTC(s) presente(s): " + ", ".join(dtc_codes[:6]))
        if urgency == "atencao":
            reasons.append("Urgência classificada como atenção")
        incomplete = readiness.get("incomplete") or []
        if incomplete:
            reasons.append(f"{len(incomplete)} monitor(es) ainda incompleto(s)")
        return InspectionVerdict(
            verdict=APROVADO_COM_RESSALVAS,
            label=LABELS[APROVADO_COM_RESSALVAS],
            reasons=reasons,
            recommendation=(
                "O veículo roda, mas as falhas listadas devem ser orçadas e "
                "consideradas na negociação. Consulte a triagem guiada do laudo."
            ),
        )

    reasons.append("Sem DTCs armazenados, pendentes ou permanentes")
    if clear_verdict == "normal":
        reasons.append("Sem indício de limpeza recente de códigos")
    incomplete = readiness.get("incomplete") or []
    if incomplete:
        reasons.append(
            f"{len(incomplete)} monitor(es) incompleto(s) — sem demais sinais de limpeza"
        )
    return InspectionVerdict(
        verdict=APROVADO,
        label=LABELS[APROVADO],
        reasons=reasons,
        recommendation="Nenhum impedimento encontrado no diagnóstico eletrônico.",
    )
