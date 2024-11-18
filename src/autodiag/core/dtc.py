from dataclasses import dataclass, field


@dataclass
class DTCInfo:
    code: str
    description: str
    severity: str  # "critico", "atencao", "informativo"
    system: str
    causes: list[str] = field(default_factory=list)


DTC_DATABASE: dict[str, DTCInfo] = {
    # ── Ar / Combustível ──────────────────────────────────────────
    "P0100": DTCInfo("P0100", "Sensor MAF — circuito com falha", "atencao", "Motor",
                     ["Sensor MAF sujo ou defeituoso", "Fiação com mau contato"]),
    "P0101": DTCInfo("P0101", "Sensor MAF — fora da faixa", "atencao", "Motor",
                     ["Sensor MAF sujo", "Vazamento de admissão", "Filtro de ar entupido"]),
    "P0102": DTCInfo("P0102", "Sensor MAF — sinal baixo", "atencao", "Motor",
                     ["Sensor MAF defeituoso", "Circuito aberto"]),
    "P0103": DTCInfo("P0103", "Sensor MAF — sinal alto", "atencao", "Motor",
                     ["Curto no circuito do MAF", "Sensor defeituoso"]),
    "P0106": DTCInfo("P0106", "Sensor MAP — fora da faixa", "atencao", "Motor",
                     ["Sensor MAP defeituoso", "Mangueira de vácuo vazando"]),
    "P0107": DTCInfo("P0107", "Sensor MAP — sinal baixo", "atencao", "Motor",
                     ["Curto no circuito", "Sensor MAP defeituoso"]),
    "P0108": DTCInfo("P0108", "Sensor MAP — sinal alto", "atencao", "Motor",
                     ["Circuito aberto", "Sensor MAP defeituoso"]),
    "P0110": DTCInfo("P0110", "Sensor de temperatura do ar de admissão — circuito", "informativo", "Motor",
                     ["Sensor IAT defeituoso", "Fiação com problema"]),
    "P0112": DTCInfo("P0112", "Sensor IAT — sinal baixo", "informativo", "Motor",
                     ["Curto no circuito do sensor IAT"]),
    "P0113": DTCInfo("P0113", "Sensor IAT — sinal alto", "informativo", "Motor",
                     ["Circuito aberto do sensor IAT"]),

    # ── Temperatura ───────────────────────────────────────────────
    "P0115": DTCInfo("P0115", "Sensor de temperatura do líquido de arrefecimento — circuito", "atencao", "Arrefecimento",
                     ["Sensor ECT defeituoso", "Fiação com falha"]),
    "P0116": DTCInfo("P0116", "Sensor ECT — fora da faixa", "atencao", "Arrefecimento",
                     ["Termostato emperrado aberto", "Sensor ECT defeituoso"]),
    "P0117": DTCInfo("P0117", "Sensor ECT — sinal baixo", "atencao", "Arrefecimento",
                     ["Curto no circuito ECT", "Sensor defeituoso"]),
    "P0118": DTCInfo("P0118", "Sensor ECT — sinal alto", "atencao", "Arrefecimento",
                     ["Circuito aberto", "Sensor ECT defeituoso"]),

    # ── Sonda Lambda / Mistura ────────────────────────────────────
    "P0130": DTCInfo("P0130", "Sonda lambda B1S1 — circuito com falha", "atencao", "Emissões",
                     ["Sonda lambda B1S1 defeituosa", "Fiação com mau contato"]),
    "P0131": DTCInfo("P0131", "Sonda lambda B1S1 — sinal baixo", "atencao", "Emissões",
                     ["Mistura pobre", "Sonda defeituosa", "Vazamento de ar"]),
    "P0132": DTCInfo("P0132", "Sonda lambda B1S1 — sinal alto", "atencao", "Emissões",
                     ["Mistura rica", "Injetor vazando", "Sonda defeituosa"]),
    "P0133": DTCInfo("P0133", "Sonda lambda B1S1 — resposta lenta", "atencao", "Emissões",
                     ["Sonda lambda envelhecida", "Contaminação por silício"]),
    "P0136": DTCInfo("P0136", "Sonda lambda B1S2 — circuito com falha", "informativo", "Emissões",
                     ["Sonda lambda B1S2 defeituosa"]),
    "P0141": DTCInfo("P0141", "Aquecedor da sonda B1S2 — circuito com falha", "informativo", "Emissões",
                     ["Resistência de aquecimento queimada", "Fusível queimado"]),
    "P0171": DTCInfo("P0171", "Mistura pobre — banco 1", "atencao", "Motor/Emissões",
                     ["Sensor MAF sujo", "Vazamento de vácuo", "Filtro de combustível entupido",
                      "Bomba de combustível fraca", "Injetor entupido"]),
    "P0172": DTCInfo("P0172", "Mistura rica — banco 1", "atencao", "Motor/Emissões",
                     ["Injetor vazando", "Sensor MAF defeituoso", "Pressão de combustível alta",
                      "Sonda lambda B1S1 defeituosa"]),
    "P0174": DTCInfo("P0174", "Mistura pobre — banco 2", "atencao", "Motor/Emissões",
                     ["Vazamento de vácuo B2", "MAF sujo", "Injetor B2 entupido"]),
    "P0175": DTCInfo("P0175", "Mistura rica — banco 2", "atencao", "Motor/Emissões",
                     ["Injetor B2 vazando", "Pressão de combustível alta"]),

    # ── Rotação / Ignição ─────────────────────────────────────────
    "P0300": DTCInfo("P0300", "Falha de ignição aleatória/múltiplos cilindros", "critico", "Motor/Ignição",
                     ["Velas desgastadas", "Cabos de ignição ruins", "Bobinas defeituosas",
                      "Injetores com falha", "Compressão baixa"]),
    "P0301": DTCInfo("P0301", "Falha de ignição — cilindro 1", "critico", "Motor/Ignição",
                     ["Vela do cilindro 1 defeituosa", "Bobina C1 com falha", "Injetor C1 entupido"]),
    "P0302": DTCInfo("P0302", "Falha de ignição — cilindro 2", "critico", "Motor/Ignição",
                     ["Vela do cilindro 2 defeituosa", "Bobina C2 com falha"]),
    "P0303": DTCInfo("P0303", "Falha de ignição — cilindro 3", "critico", "Motor/Ignição",
                     ["Vela do cilindro 3 defeituosa", "Bobina C3 com falha"]),
    "P0304": DTCInfo("P0304", "Falha de ignição — cilindro 4", "critico", "Motor/Ignição",
                     ["Vela do cilindro 4 defeituosa", "Bobina C4 com falha"]),
    "P0316": DTCInfo("P0316", "Falha de ignição na partida (primeiros 1000 giros)", "atencao", "Motor/Ignição",
                     ["Velas desgastadas", "Problema de compressão"]),

    # ── Marcha Lenta ──────────────────────────────────────────────
    "P0505": DTCInfo("P0505", "Sistema de controle de marcha lenta — circuito", "atencao", "Motor",
                     ["Válvula IAC defeituosa", "Corpo de borboleta sujo"]),
    "P0506": DTCInfo("P0506", "RPM de marcha lenta abaixo do esperado", "atencao", "Motor",
                     ["Corpo de borboleta sujo", "Válvula IAC entupida", "Vazamento de vácuo"]),
    "P0507": DTCInfo("P0507", "RPM de marcha lenta acima do esperado", "atencao", "Motor",
                     ["Válvula IAC travada aberta", "Vazamento de ar pós-borboleta"]),

    # ── EGR / Emissões ────────────────────────────────────────────
    "P0400": DTCInfo("P0400", "Sistema EGR — fluxo insuficiente", "atencao", "Emissões",
                     ["Válvula EGR entupida", "Mangueira EGR obstruída"]),
    "P0401": DTCInfo("P0401", "Sistema EGR — fluxo abaixo do esperado", "atencao", "Emissões",
                     ["Válvula EGR com depósito de carbono", "Sensor DPFE defeituoso"]),
    "P0402": DTCInfo("P0402", "Sistema EGR — fluxo acima do esperado", "atencao", "Emissões",
                     ["Válvula EGR travada aberta"]),
    "P0420": DTCInfo("P0420", "Eficiência do catalisador abaixo do limite — banco 1", "atencao", "Emissões",
                     ["Catalisador (catalizador) desgastado", "Sonda pós-cat defeituosa",
                      "Vazamento no escapamento"]),
    "P0430": DTCInfo("P0430", "Eficiência do catalisador abaixo do limite — banco 2", "atencao", "Emissões",
                     ["Catalisador B2 desgastado"]),

    # ── EVAP ──────────────────────────────────────────────────────
    "P0440": DTCInfo("P0440", "Sistema EVAP — vazamento detectado", "informativo", "Emissões",
                     ["Tampa do tanque de combustível mal fechada", "Mangueiras EVAP rachadas"]),
    "P0441": DTCInfo("P0441", "Sistema EVAP — controle de purga incorreto", "informativo", "Emissões",
                     ["Válvula de purga EVAP defeituosa"]),
    "P0442": DTCInfo("P0442", "Sistema EVAP — vazamento pequeno detectado", "informativo", "Emissões",
                     ["Tampa do tanque solta", "O-ring do bocal com falha"]),
    "P0455": DTCInfo("P0455", "Sistema EVAP — vazamento grande detectado", "atencao", "Emissões",
                     ["Tampa do tanque ausente/danificada", "Cânister EVAP com problema"]),
    "P0456": DTCInfo("P0456", "Sistema EVAP — vazamento muito pequeno", "informativo", "Emissões",
                     ["Tampa do tanque sem vedação adequada"]),

    # ── Câmbio / Transmissão ──────────────────────────────────────
    "P0700": DTCInfo("P0700", "Módulo de controle da transmissão — falha genérica", "critico", "Transmissão",
                     ["Verificar DTCs específicos da transmissão", "TCM com problema"]),
    "P0711": DTCInfo("P0711", "Sensor de temperatura do fluido da transmissão — faixa", "atencao", "Transmissão",
                     ["Sensor TFT defeituoso", "Fiação com falha"]),
    "P0720": DTCInfo("P0720", "Sensor de velocidade do eixo de saída — circuito", "atencao", "Transmissão",
                     ["Sensor OSS defeituoso", "Anel fônico danificado"]),
    "P0730": DTCInfo("P0730", "Proporção de marcha incorreta", "critico", "Transmissão",
                     ["Solenoides da transmissão com falha", "Fluido contaminado"]),
    "P0740": DTCInfo("P0740", "Solenóide do conversor de torque — circuito elétrico", "critico", "Transmissão",
                     ["Solenóide TCC defeituoso", "Fiação com curto/aberto", "Válvula TCC travada"]),
    "P0741": DTCInfo("P0741", "Solenóide do conversor de torque — emperrado aberto", "critico", "Transmissão",
                     ["Solenóide TCC defeituoso", "Fluido de transmissão degradado"]),
    "P0750": DTCInfo("P0750", "Solenóide de troca A — circuito elétrico", "critico", "Transmissão",
                     ["Solenóide SS-A defeituoso", "Fiação com problema"]),
    "P0755": DTCInfo("P0755", "Solenóide de troca B — circuito elétrico", "critico", "Transmissão",
                     ["Solenóide SS-B defeituoso"]),

    # ── Rede CAN / Comunicação ────────────────────────────────────
    "U0001": DTCInfo("U0001", "Barramento CAN de alta velocidade — falha de comunicação", "critico", "Rede/Eletrônica",
                     ["Fiação do barramento CAN danificada", "Módulo com falha no barramento"]),
    "U0100": DTCInfo("U0100", "Sem comunicação com ECM/PCM", "critico", "Rede/Eletrônica",
                     ["ECM/PCM sem alimentação ou terra", "Barramento CAN com problema"]),
    "U0101": DTCInfo("U0101", "Sem comunicação com TCM", "critico", "Rede/Eletrônica",
                     ["TCM sem alimentação", "Fiação CAN com falha"]),
    "U0121": DTCInfo("U0121", "Sem comunicação com módulo de controle ABS", "atencao", "Rede/Eletrônica",
                     ["Módulo ABS sem alimentação", "Barramento CAN interrompido"]),
    "U0140": DTCInfo("U0140", "Sem comunicação com módulo de carroceria (BCM)", "atencao", "Rede/Eletrônica",
                     ["BCM sem energia", "Falha de comunicação CAN"]),

    # ── ABS / Freios ──────────────────────────────────────────────
    "C0031": DTCInfo("C0031", "Sensor de velocidade da roda dianteira esquerda — circuito", "critico", "Freios/ABS",
                     ["Sensor ABS defeituoso", "Anel fônico danificado", "Fiação com falha"]),
    "C0034": DTCInfo("C0034", "Sensor de velocidade da roda dianteira direita — circuito", "critico", "Freios/ABS",
                     ["Sensor ABS defeituoso", "Anel fônico danificado"]),
    "C0037": DTCInfo("C0037", "Sensor de velocidade da roda traseira esquerda — circuito", "critico", "Freios/ABS",
                     ["Sensor ABS defeituoso"]),
    "C0040": DTCInfo("C0040", "Sensor de velocidade da roda traseira direita — circuito", "critico", "Freios/ABS",
                     ["Sensor ABS defeituoso"]),

    # ── Airbag / Carroceria ───────────────────────────────────────
    "B0001": DTCInfo("B0001", "Airbag do motorista — circuito com falha", "critico", "Airbag",
                     ["Conector do airbag solto", "Espiral do volante defeituosa"]),
    "B0002": DTCInfo("B0002", "Airbag do passageiro — circuito com falha", "critico", "Airbag",
                     ["Conector do airbag solto"]),
    "B1001": DTCInfo("B1001", "Módulo de controle do airbag — falha interna", "critico", "Airbag",
                     ["Módulo SRS defeituoso"]),

    # ── Direção Elétrica ──────────────────────────────────────────
    "C0460": DTCInfo("C0460", "Sensor de torque da direção — circuito", "atencao", "Direção",
                     ["Sensor de torque EPS defeituoso", "Fiação com problema"]),
    "C0900": DTCInfo("C0900", "Módulo de direção elétrica — falha interna", "critico", "Direção",
                     ["Módulo EPS defeituoso"]),
}


def lookup(code: str) -> DTCInfo | None:
    return DTC_DATABASE.get(code.upper().strip())


def severity_color(severity: str) -> str:
    return {"critico": "red", "atencao": "yellow", "informativo": "cyan"}.get(severity, "white")
