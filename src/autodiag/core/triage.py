from dataclasses import asdict, dataclass

from autodiag.elm327.reader import DTCRecord, LivePIDs


@dataclass(frozen=True)
class Observation:
    label: str
    value: str
    severity: str = "informativo"


@dataclass(frozen=True)
class GuidedTriage:
    headline: str
    drive_advice: str
    observations: list[Observation]
    likely_causes: list[str]
    recommended_tests: list[str]
    dont_do: list[str]

    def as_dict(self) -> dict:
        data = asdict(self)
        data["observations"] = [asdict(o) for o in self.observations]
        return data


def build_guided_triage(dtcs: list[DTCRecord], pids: LivePIDs, urgency: str) -> dict:
    codes = {d.code for d in dtcs}

    observations: list[Observation] = []
    likely_causes: list[str] = []
    recommended_tests: list[str] = []
    dont_do: list[str] = []

    if pids.coolant_temp_c is not None and pids.coolant_temp_c >= 106:
        observations.append(
            Observation("Temperatura do motor", f"{pids.coolant_temp_c} °C", "critico")
        )
        likely_causes += [
            "Baixo nível de líquido de arrefecimento / vazamento",
            "Ventoinha não acionando",
            "Válvula termostática travada",
            "Bomba d'água ineficiente",
        ]
        recommended_tests += [
            "Verificar nível do líquido e sinais de vazamento (mangueiras, radiador, reservatório)",
            "Conferir acionamento da ventoinha e fusíveis/relés",
            "Conferir termostática (temperaturas de mangueiras e aquecimento)",
        ]
        dont_do += [
            "Não continuar rodando com temperatura alta (risco de empeno/junta)",
            "Não abrir o reservatório com o motor quente",
        ]

    is_misfire = any(code.startswith("P030") for code in codes)
    if is_misfire:
        likely_causes += [
            "Falha de ignição (vela, bobina, cabo)",
            "Entrada falsa de ar",
            "Mistura fora do ideal (MAF, combustível, pressão)",
        ]
        recommended_tests += [
            "Inspecionar velas/bobinas (e trocar de cilindro para ver se o código acompanha)",
            "Checar conectores e aterramentos do conjunto de ignição",
            "Verificar MAF e pressão de combustível se houver P0171/P0174 junto",
        ]
        dont_do += [
            "Não insistir em rodar com falha de ignição (pode danificar catalisador)",
            "Não trocar múltiplas peças sem isolar o cilindro/causa",
        ]

    is_lean = bool(codes & {"P0171", "P0174"})
    if is_lean:
        stft = pids.fuel_trim_short_b1
        ltft = pids.fuel_trim_long_b1
        if stft is not None:
            sev = "atencao" if abs(stft) > 15 else "informativo"
            observations.append(Observation("Fuel trim curto B1", f"{stft:.1f} %", sev))
        if ltft is not None:
            sev = "atencao" if abs(ltft) > 10 else "informativo"
            observations.append(Observation("Fuel trim longo B1", f"{ltft:.1f} %", sev))
        if pids.maf_g_s is not None:
            sev = "atencao" if pids.maf_g_s < 2.0 else "informativo"
            observations.append(Observation("MAF", f"{pids.maf_g_s:.2f} g/s", sev))

        likely_causes += [
            "Entrada falsa de ar após o MAF (mangueiras, juntas, coletor)",
            "PCV/válvula de respiro travada",
            "MAF sujo/descalibrado",
            "Pressão de combustível baixa / filtro restrito",
        ]
        recommended_tests += [
            "Inspecionar mangueiras e juntas de admissão (ideal: teste de fumaça)",
            "Verificar PCV e mangueiras de respiro",
            "Limpar o MAF com produto adequado (sem tocar no elemento) e reavaliar trims",
            "Medir pressão de combustível (se disponível) e checar filtro/bomba",
        ]
        dont_do += [
            "Não trocar sonda O2 como primeira ação sem validar mistura e entrada falsa de ar",
        ]

    is_rich = bool(codes & {"P0172", "P0175"})
    if is_rich:
        likely_causes += [
            "MAF superestimando fluxo",
            "Injetor gotejando / pressão alta",
            "Sensor de temperatura enganando enriquecimento",
        ]
        recommended_tests += [
            "Verificar leituras de MAF e trims em marcha lenta e sob carga",
            "Checar pressão de combustível e vedação de injetores",
        ]
        dont_do += [
            "Não trocar catalisador antes de corrigir mistura rica",
        ]

    if codes & {"P0420", "P0430"}:
        likely_causes += [
            "Eficiência do catalisador baixa",
            "Falha de ignição/mistura fora do ideal danificando catalisador",
            "Vazamento de escapamento antes da sonda",
        ]
        recommended_tests += [
            "Verificar se há misfire e trims fora do padrão antes de condenar catalisador",
            "Inspecionar vazamentos no escapamento e integridade das sondas",
        ]
        dont_do += [
            "Não condenar catalisador sem checar misfire/trims e vazamentos de escapamento",
        ]

    headline = "Scan limpo"
    if dtcs:
        headline = "Códigos de falha detectados"
    if is_lean and is_misfire:
        headline = "Mistura pobre + falha de ignição (padrão recorrente)"
    elif is_lean:
        headline = "Mistura pobre (fuel trim alto)"
    elif is_misfire:
        headline = "Falha de ignição (misfire)"
    elif pids.coolant_temp_c is not None and pids.coolant_temp_c >= 106:
        headline = "Superaquecimento detectado"

    drive_advice = "pode_rodar"
    if urgency == "critico" or (pids.coolant_temp_c is not None and pids.coolant_temp_c >= 106):
        drive_advice = "pare"
    elif urgency == "atencao" or dtcs:
        drive_advice = "cautela"

    def _dedupe(items: list[str]) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for item in items:
            key = item.strip().lower()
            if not key or key in seen:
                continue
            seen.add(key)
            out.append(item)
        return out

    triage = GuidedTriage(
        headline=headline,
        drive_advice=drive_advice,
        observations=observations,
        likely_causes=_dedupe(likely_causes),
        recommended_tests=_dedupe(recommended_tests),
        dont_do=_dedupe(dont_do),
    )
    return triage.as_dict()

