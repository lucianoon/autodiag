"""
Catálogo estendido de DTCs genéricos (SAE J2012), gerado por tabelas de família.

Os códigos genéricos OBD2 seguem padrões estruturais definidos pela SAE:
sensores têm quintetos de circuito (falha / faixa / baixo / alto /
intermitente), sondas lambda têm sextetos por banco/sensor, injetores e
falhas de ignição são indexados por cilindro, solenoides de câmbio seguem
o mesmo padrão de 5 estados, e códigos U0xxx derivam de uma tabela de
módulos. Este módulo materializa essas famílias em descrições PT-BR com
severidade e causas prováveis por tipo de falha.

A base curada em ``core/dtc.py`` (revisada manualmente, com causas mais
específicas) tem precedência sobre o que é gerado aqui — ver
``dtc.full_database()``.
"""
from functools import lru_cache

from autodiag.core.dtc import DTCInfo

# Sufixos do quinteto padrão SAE para sensores/circuitos.
_Q5 = (
    "circuito com falha",
    "faixa/desempenho fora do esperado",
    "sinal baixo no circuito",
    "sinal alto no circuito",
    "circuito intermitente",
)

# Sufixos do padrão de 5 estados para solenoides (câmbio, TCC, pressão).
_SOL5 = (
    "com falha",
    "desempenho anormal ou travado desligado",
    "travado ligado",
    "circuito elétrico com falha",
    "circuito intermitente",
)

# Sexteto padrão de sonda lambda por banco/sensor.
_O2_6 = (
    "circuito com falha",
    "tensão baixa",
    "tensão alta",
    "resposta lenta",
    "sem atividade detectada",
    "aquecedor — circuito com falha",
)


def _causes_q5(comp: str, idx: int) -> list[str]:
    return [
        [f"{comp} defeituoso", "Fiação ou conector com mau contato"],
        [f"{comp} sujo ou degradado", "Condição mecânica fora da faixa de operação"],
        ["Curto ao terra no circuito", f"{comp} defeituoso"],
        ["Circuito aberto ou curto ao positivo", f"{comp} defeituoso"],
        ["Mau contato intermitente no chicote ou conector"],
    ][idx]


# (código inicial, quantidade de sufixos usados, componente, sistema, severidade)
_QUINTETOS: tuple[tuple[str, int, str, str, str], ...] = (
    ("P0001", 4, "Regulador de volume de combustível", "Combustível", "atencao"),
    ("P0100", 5, "Sensor MAF (fluxo de ar)", "Motor", "atencao"),
    ("P0105", 5, "Sensor MAP (pressão do coletor)", "Motor", "atencao"),
    ("P0110", 5, "Sensor IAT (temperatura do ar de admissão)", "Motor", "informativo"),
    ("P0115", 5, "Sensor ECT (temperatura do arrefecimento)", "Arrefecimento", "atencao"),
    ("P0120", 5, "Sensor de posição da borboleta/pedal A", "Motor", "atencao"),
    ("P0180", 5, "Sensor de temperatura do combustível A", "Combustível", "informativo"),
    ("P0185", 5, "Sensor de temperatura do combustível B", "Combustível", "informativo"),
    ("P0190", 5, "Sensor de pressão da flauta de combustível", "Combustível", "atencao"),
    ("P0195", 5, "Sensor de temperatura do óleo do motor", "Motor", "informativo"),
    ("P0220", 5, "Sensor de posição da borboleta/pedal B", "Motor", "atencao"),
    ("P0225", 5, "Sensor de posição da borboleta/pedal C", "Motor", "atencao"),
    ("P0325", 5, "Sensor de detonação 1 (banco 1)", "Motor/Ignição", "atencao"),
    ("P0330", 5, "Sensor de detonação 2 (banco 2)", "Motor/Ignição", "atencao"),
    ("P0335", 5, "Sensor de posição do virabrequim A", "Motor/Ignição", "critico"),
    ("P0340", 5, "Sensor de posição do comando de válvulas A (banco 1)",
     "Motor/Ignição", "critico"),
    ("P0345", 5, "Sensor de posição do comando de válvulas A (banco 2)",
     "Motor/Ignição", "critico"),
    ("P0365", 5, "Sensor de posição do comando de válvulas B (banco 1)",
     "Motor/Ignição", "atencao"),
    ("P0390", 5, "Sensor de posição do comando de válvulas B (banco 2)",
     "Motor/Ignição", "atencao"),
    ("P0460", 5, "Sensor de nível de combustível", "Combustível", "informativo"),
    ("P0470", 5, "Sensor de pressão do escapamento", "Emissões", "informativo"),
    ("P0500", 4, "Sensor de velocidade do veículo (VSS) A", "Motor", "atencao"),
    ("P0520", 4, "Sensor/interruptor de pressão do óleo", "Motor", "critico"),
    ("P0530", 4, "Sensor de pressão do A/C", "Climatização", "informativo"),
    ("P0550", 5, "Sensor de pressão da direção hidráulica", "Direção", "atencao"),
    ("P0705", 5, "Sensor de posição/faixa da transmissão (PRNDL)", "Transmissão", "atencao"),
    ("P0710", 5, "Sensor de temperatura do fluido da transmissão", "Transmissão", "atencao"),
    ("P0715", 5, "Sensor de rotação de entrada da transmissão", "Transmissão", "atencao"),
    ("P0720", 4, "Sensor de velocidade do eixo de saída (OSS)", "Transmissão", "atencao"),
    ("P0725", 4, "Sinal de rotação do motor para a transmissão", "Transmissão", "atencao"),
)

# Solenoides do câmbio: (código inicial, nome, sistema)
_SOLENOIDES: tuple[tuple[str, str], ...] = (
    ("P0740", "Solenóide do conversor de torque (TCC)"),
    ("P0745", "Solenóide de controle de pressão A"),
    ("P0750", "Solenóide de troca A"),
    ("P0755", "Solenóide de troca B"),
    ("P0760", "Solenóide de troca C"),
    ("P0765", "Solenóide de troca D"),
    ("P0770", "Solenóide de troca E"),
    ("P0775", "Solenóide de controle de pressão B"),
    ("P0795", "Solenóide de controle de pressão C"),
)

# Sondas lambda: (código inicial, banco, sensor)
_SONDAS: tuple[tuple[str, int, int], ...] = (
    ("P0130", 1, 1),
    ("P0136", 1, 2),
    ("P0142", 1, 3),
    ("P0150", 2, 1),
    ("P0156", 2, 2),
    ("P0162", 2, 3),
)

# Controle do aquecedor da sonda: (código inicial, banco, sensor)
_AQUECEDORES: tuple[tuple[str, int, int], ...] = (
    ("P0030", 1, 1),
    ("P0036", 1, 2),
    ("P0050", 2, 1),
    ("P0056", 2, 2),
)

# Módulos de rede para U01xx/U02xx ("Perda de comunicação com X").
# Severidade "critico" quando a perda compromete tração, freio ou segurança.
_MODULOS_REDE: dict[str, tuple[str, str]] = {
    "U0100": ("ECM/PCM A (módulo do motor)", "critico"),
    "U0101": ("TCM (módulo da transmissão)", "critico"),
    "U0102": ("módulo da caixa de transferência", "atencao"),
    "U0103": ("módulo do seletor de marcha", "critico"),
    "U0104": ("módulo do controle de cruzeiro", "atencao"),
    "U0105": ("módulo de controle dos injetores", "critico"),
    "U0106": ("módulo das velas aquecedoras (glow)", "atencao"),
    "U0107": ("módulo do atuador da borboleta", "critico"),
    "U0109": ("módulo da bomba de combustível", "critico"),
    "U0110": ("módulo do motor elétrico de tração", "critico"),
    "U0111": ("módulo da bateria de tração (BECM)", "critico"),
    "U0114": ("módulo da embreagem 4x4", "atencao"),
    "U0115": ("ECM/PCM B", "critico"),
    "U0121": ("módulo do ABS", "critico"),
    "U0122": ("módulo do controle de estabilidade (ESC/VDC)", "critico"),
    "U0123": ("sensor de guinada (yaw rate)", "atencao"),
    "U0124": ("acelerômetro lateral", "atencao"),
    "U0125": ("acelerômetro multi-eixo", "atencao"),
    "U0126": ("sensor de ângulo da direção", "atencao"),
    "U0128": ("módulo do freio de estacionamento", "atencao"),
    "U0129": ("módulo do sistema de freio", "critico"),
    "U0131": ("módulo da direção elétrica (EPS)", "critico"),
    "U0132": ("módulo da suspensão nivelada", "atencao"),
    "U0140": ("módulo de carroceria (BCM)", "atencao"),
    "U0141": ("módulo de carroceria (BCM) A", "atencao"),
    "U0142": ("módulo de carroceria (BCM) B", "atencao"),
    "U0146": ("gateway A da rede", "atencao"),
    "U0151": ("módulo do airbag (SRS)", "critico"),
    "U0154": ("módulo de ocupação do assento", "critico"),
    "U0155": ("painel de instrumentos (IPC)", "atencao"),
    "U0156": ("central de informações", "informativo"),
    "U0159": ("módulo do assistente de estacionamento", "informativo"),
    "U0161": ("módulo de alerta sonoro", "informativo"),
    "U0164": ("módulo de climatização (HVAC)", "informativo"),
    "U0167": ("módulo do imobilizador", "atencao"),
    "U0168": ("módulo de alarme/segurança do veículo", "atencao"),
    "U0170": ("sensor de colisão A", "critico"),
    "U0184": ("rádio/central multimídia", "informativo"),
    "U0186": ("amplificador de áudio", "informativo"),
    "U0197": ("módulo de telefone/telemática", "informativo"),
    "U0199": ("módulo da porta do motorista", "informativo"),
    "U0200": ("módulo da porta do passageiro", "informativo"),
    "U0208": ("módulo do assento A", "informativo"),
    "U0214": ("receptor de funções remotas", "informativo"),
    "U0230": ("módulo da tampa traseira", "informativo"),
    "U0235": ("sensor frontal do cruzeiro adaptativo (radar)", "atencao"),
    "U0245": ("câmera frontal", "atencao"),
    "U0293": ("módulo de controle do sistema híbrido", "critico"),
}

# Entradas explícitas: códigos comuns que não seguem padrão de família.
# (código, descrição, severidade, sistema, causas)
_EXPLICITOS: tuple[tuple[str, str, str, str, list[str]], ...] = (
    # ── VVT / sincronismo ─────────────────────────────────────────
    ("P0010", "Atuador de comando variável (VVT) A — circuito — banco 1", "atencao", "Motor",
     ["Solenóide VVT defeituoso", "Óleo degradado ou nível baixo"]),
    ("P0011", "Comando A banco 1 — sincronismo super avançado", "atencao", "Motor",
     ["Solenóide VVT travado", "Óleo incorreto ou degradado", "Corrente esticada"]),
    ("P0012", "Comando A banco 1 — sincronismo super atrasado", "atencao", "Motor",
     ["Solenóide VVT travado", "Óleo degradado", "Tensionador da corrente com folga"]),
    ("P0013", "Atuador de comando variável (VVT) B — circuito — banco 1", "atencao", "Motor",
     ["Solenóide VVT defeituoso", "Fiação com mau contato"]),
    ("P0014", "Comando B banco 1 — sincronismo super avançado", "atencao", "Motor",
     ["Solenóide VVT travado", "Óleo degradado"]),
    ("P0015", "Comando B banco 1 — sincronismo super atrasado", "atencao", "Motor",
     ["Solenóide VVT travado", "Óleo degradado"]),
    ("P0016", "Correlação virabrequim/comando A — banco 1", "critico", "Motor",
     ["Corrente/correia fora do ponto", "Anel fônico deslocado", "Tensionador com falha"]),
    ("P0017", "Correlação virabrequim/comando B — banco 1", "critico", "Motor",
     ["Corrente/correia fora do ponto", "Tensionador com falha"]),
    ("P0018", "Correlação virabrequim/comando A — banco 2", "critico", "Motor",
     ["Corrente/correia fora do ponto"]),
    ("P0019", "Correlação virabrequim/comando B — banco 2", "critico", "Motor",
     ["Corrente/correia fora do ponto"]),
    ("P0020", "Atuador de comando variável (VVT) A — circuito — banco 2", "atencao", "Motor",
     ["Solenóide VVT defeituoso"]),
    ("P0021", "Comando A banco 2 — sincronismo super avançado", "atencao", "Motor",
     ["Solenóide VVT travado", "Óleo degradado"]),
    ("P0022", "Comando A banco 2 — sincronismo super atrasado", "atencao", "Motor",
     ["Solenóide VVT travado", "Óleo degradado"]),
    # ── Turbo / sobrealimentação ──────────────────────────────────
    ("P0033", "Válvula de alívio do turbo (bypass) — circuito", "atencao", "Motor",
     ["Válvula de alívio defeituosa", "Fiação com falha"]),
    ("P0034", "Válvula de alívio do turbo — sinal baixo", "atencao", "Motor",
     ["Curto ao terra no circuito"]),
    ("P0035", "Válvula de alívio do turbo — sinal alto", "atencao", "Motor",
     ["Circuito aberto"]),
    ("P0045", "Solenóide de controle do turbo A — circuito", "atencao", "Motor",
     ["Solenóide de controle defeituoso"]),
    ("P0046", "Solenóide de controle do turbo A — faixa/desempenho", "atencao", "Motor",
     ["Atuador da geometria variável travado", "Mangueira de controle vazando"]),
    ("P0047", "Solenóide de controle do turbo A — sinal baixo", "atencao", "Motor",
     ["Curto ao terra no circuito"]),
    ("P0048", "Solenóide de controle do turbo A — sinal alto", "atencao", "Motor",
     ["Circuito aberto"]),
    ("P0234", "Sobrepressão do turbo (overboost)", "critico", "Motor",
     ["Wastegate travada fechada", "Solenóide de controle com falha",
      "Mangueira de controle solta"]),
    ("P0243", "Solenóide da wastegate A — circuito", "atencao", "Motor",
     ["Solenóide defeituoso", "Fiação com falha"]),
    ("P0299", "Pressão do turbo abaixo do esperado (underboost)", "atencao", "Motor",
     ["Vazamento no circuito de pressão", "Wastegate travada aberta", "Turbo desgastado"]),
    # ── Combustível / pressão ─────────────────────────────────────
    ("P0087", "Pressão da flauta/sistema de combustível muito baixa", "critico", "Combustível",
     ["Bomba de alta pressão fraca", "Filtro entupido", "Regulador de pressão com falha"]),
    ("P0088", "Pressão da flauta/sistema de combustível muito alta", "critico", "Combustível",
     ["Regulador de pressão travado", "Válvula de retorno obstruída"]),
    ("P0089", "Regulador de pressão de combustível 1 — desempenho", "atencao", "Combustível",
     ["Regulador de pressão desgastado", "Detritos na válvula"]),
    ("P0090", "Regulador de pressão de combustível 1 — circuito de controle", "atencao",
     "Combustível",
     ["Fiação com falha", "Regulador defeituoso"]),
    ("P0091", "Regulador de pressão de combustível 1 — controle baixo", "atencao", "Combustível",
     ["Curto ao terra no circuito"]),
    ("P0092", "Regulador de pressão de combustível 1 — controle alto", "atencao", "Combustível",
     ["Circuito aberto"]),
    ("P0230", "Bomba de combustível — circuito primário", "critico", "Combustível",
     ["Relé da bomba defeituoso", "Fiação com falha"]),
    ("P0231", "Bomba de combustível — circuito secundário baixo", "atencao", "Combustível",
     ["Curto ao terra", "Relé defeituoso"]),
    ("P0232", "Bomba de combustível — circuito secundário alto", "atencao", "Combustível",
     ["Curto ao positivo"]),
    # ── Correlações / ar ──────────────────────────────────────────
    ("P0068", "Correlação MAP/MAF x posição da borboleta", "atencao", "Motor",
     ["Vazamento de admissão", "Sensor MAP ou MAF impreciso", "Corpo de borboleta sujo"]),
    ("P0069", "Correlação pressão do coletor x pressão barométrica", "atencao", "Motor",
     ["Sensor MAP defeituoso", "Mangueira de vácuo vazando"]),
    ("P0071", "Sensor de temperatura ambiente — faixa/desempenho", "informativo", "Motor",
     ["Sensor de temperatura ambiente defeituoso"]),
    ("P0072", "Sensor de temperatura ambiente — sinal baixo", "informativo", "Motor",
     ["Curto ao terra no circuito"]),
    ("P0073", "Sensor de temperatura ambiente — sinal alto", "informativo", "Motor",
     ["Circuito aberto"]),
    # ── Mistura (complementa a base curada) ───────────────────────
    ("P0170", "Ajuste de combustível (fuel trim) — banco 1", "atencao", "Motor/Emissões",
     ["Vazamento de vácuo", "Sensor MAF impreciso", "Pressão de combustível fora da faixa"]),
    ("P0173", "Ajuste de combustível (fuel trim) — banco 2", "atencao", "Motor/Emissões",
     ["Vazamento de vácuo no banco 2", "Sensor MAF impreciso"]),
    # ── Temperatura / termostato ──────────────────────────────────
    ("P0125", "Temperatura insuficiente para controle em malha fechada", "atencao", "Arrefecimento",
     ["Termostato emperrado aberto", "Sensor ECT impreciso", "Nível baixo de arrefecimento"]),
    ("P0126", "Temperatura insuficiente para operação estável", "atencao", "Arrefecimento",
     ["Termostato emperrado aberto"]),
    ("P0128", "Termostato — temperatura abaixo da regulagem", "atencao", "Arrefecimento",
     ["Termostato emperrado aberto", "Sensor ECT impreciso"]),
    # ── Ignição / partida ─────────────────────────────────────────
    ("P0350", "Bobina de ignição — circuito primário/secundário", "atencao", "Motor/Ignição",
     ["Bobina defeituosa", "Fiação com mau contato"]),
    ("P0380", "Velas aquecedoras (glow) — circuito A", "atencao", "Motor",
     ["Vela aquecedora queimada", "Relé das velas com falha"]),
    ("P0381", "Lâmpada indicadora das velas aquecedoras — circuito", "informativo", "Motor",
     ["Lâmpada queimada", "Fiação com falha"]),
    ("P0382", "Velas aquecedoras (glow) — circuito B", "atencao", "Motor",
     ["Vela aquecedora queimada"]),
    # ── EGR / ar secundário / catalisador ─────────────────────────
    ("P0403", "Válvula EGR — circuito de controle", "atencao", "Emissões",
     ["Solenóide EGR defeituoso", "Fiação com falha"]),
    ("P0404", "Válvula EGR — faixa/desempenho", "atencao", "Emissões",
     ["Válvula EGR com depósito de carbono", "Sensor de posição impreciso"]),
    ("P0405", "Sensor de posição da EGR A — sinal baixo", "atencao", "Emissões",
     ["Curto ao terra no circuito", "Sensor defeituoso"]),
    ("P0406", "Sensor de posição da EGR A — sinal alto", "atencao", "Emissões",
     ["Circuito aberto", "Sensor defeituoso"]),
    ("P0410", "Sistema de ar secundário — falha", "atencao", "Emissões",
     ["Bomba de ar secundário defeituosa", "Válvula de retenção travada"]),
    ("P0411", "Sistema de ar secundário — fluxo incorreto", "atencao", "Emissões",
     ["Mangueira obstruída ou vazando", "Válvula comutadora com falha"]),
    ("P0412", "Válvula comutadora de ar secundário A — circuito", "informativo", "Emissões",
     ["Solenóide defeituoso", "Fiação com falha"]),
    ("P0413", "Válvula comutadora de ar secundário A — circuito aberto", "informativo", "Emissões",
     ["Circuito aberto"]),
    ("P0414", "Válvula comutadora de ar secundário A — curto", "informativo", "Emissões",
     ["Curto no circuito"]),
    ("P0418", "Relé da bomba de ar secundário A — circuito", "informativo", "Emissões",
     ["Relé defeituoso"]),
    ("P0421", "Eficiência do catalisador de aquecimento abaixo do limite — banco 1", "atencao",
     "Emissões",
     ["Catalisador desgastado", "Sonda pós-catalisador imprecisa"]),
    ("P0422", "Eficiência do catalisador principal abaixo do limite — banco 1", "atencao",
     "Emissões",
     ["Catalisador desgastado"]),
    ("P0431", "Eficiência do catalisador de aquecimento abaixo do limite — banco 2", "atencao",
     "Emissões",
     ["Catalisador desgastado"]),
    # ── EVAP (complementa a base curada) ──────────────────────────
    ("P0443", "Válvula de purga EVAP — circuito", "informativo", "Emissões",
     ["Solenóide de purga defeituoso", "Fiação com falha"]),
    ("P0444", "Válvula de purga EVAP — circuito aberto", "informativo", "Emissões",
     ["Circuito aberto"]),
    ("P0445", "Válvula de purga EVAP — curto", "informativo", "Emissões",
     ["Curto no circuito"]),
    ("P0446", "Válvula de ventilação EVAP — circuito de controle", "informativo", "Emissões",
     ["Válvula de ventilação obstruída", "Solenóide defeituoso"]),
    ("P0447", "Válvula de ventilação EVAP — circuito aberto", "informativo", "Emissões",
     ["Circuito aberto"]),
    ("P0448", "Válvula de ventilação EVAP — curto", "informativo", "Emissões",
     ["Curto no circuito"]),
    ("P0449", "Válvula de ventilação EVAP — circuito do solenóide", "informativo", "Emissões",
     ["Solenóide defeituoso"]),
    ("P0450", "Sensor de pressão do EVAP — falha", "informativo", "Emissões",
     ["Sensor de pressão defeituoso"]),
    ("P0451", "Sensor de pressão do EVAP — faixa/desempenho", "informativo", "Emissões",
     ["Sensor de pressão impreciso"]),
    ("P0452", "Sensor de pressão do EVAP — sinal baixo", "informativo", "Emissões",
     ["Curto ao terra no circuito"]),
    ("P0453", "Sensor de pressão do EVAP — sinal alto", "informativo", "Emissões",
     ["Circuito aberto"]),
    ("P0457", "Sistema EVAP — vazamento (tampa do tanque solta)", "informativo", "Emissões",
     ["Tampa do tanque solta ou mal fechada após abastecer"]),
    # ── Marcha lenta / velocidade ─────────────────────────────────
    ("P0508", "Válvula de marcha lenta (IAC) — sinal baixo", "atencao", "Motor",
     ["Curto ao terra no circuito", "Válvula IAC defeituosa"]),
    ("P0509", "Válvula de marcha lenta (IAC) — sinal alto", "atencao", "Motor",
     ["Circuito aberto", "Válvula IAC defeituosa"]),
    ("P0511", "Válvula de marcha lenta (IAC) — circuito", "atencao", "Motor",
     ["Válvula IAC defeituosa", "Fiação com falha"]),
    ("P0513", "Chave do imobilizador incorreta", "atencao", "Eletrônica",
     ["Chave não cadastrada", "Antena do imobilizador com falha"]),
    # ── Elétrica / carga ──────────────────────────────────────────
    ("P0560", "Tensão do sistema — falha", "atencao", "Elétrica",
     ["Bateria fraca", "Alternador com falha", "Mau contato nos terminais"]),
    ("P0561", "Tensão do sistema — instável", "atencao", "Elétrica",
     ["Alternador com diodo em falha", "Mau contato nos terminais"]),
    ("P0562", "Tensão do sistema — baixa", "atencao", "Elétrica",
     ["Bateria descarregada", "Alternador fraco", "Correia do alternador patinando"]),
    ("P0563", "Tensão do sistema — alta", "atencao", "Elétrica",
     ["Regulador de tensão do alternador com falha"]),
    ("P0620", "Alternador — circuito de controle", "atencao", "Elétrica",
     ["Alternador defeituoso", "Fiação com falha"]),
    ("P0621", "Alternador — lâmpada indicadora (L)", "informativo", "Elétrica",
     ["Lâmpada queimada", "Fiação com falha"]),
    ("P0622", "Alternador — campo (F) com falha", "atencao", "Elétrica",
     ["Regulador de tensão defeituoso"]),
    ("P0615", "Relé do motor de partida — circuito", "atencao", "Elétrica",
     ["Relé defeituoso", "Fiação com falha"]),
    ("P0616", "Relé do motor de partida — sinal baixo", "atencao", "Elétrica",
     ["Curto ao terra"]),
    ("P0617", "Relé do motor de partida — sinal alto", "atencao", "Elétrica",
     ["Curto ao positivo"]),
    ("P0627", "Bomba de combustível A — circuito de controle", "critico", "Combustível",
     ["Relé/driver da bomba com falha", "Fiação com falha"]),
    ("P0642", "Tensão de referência dos sensores A — baixa", "critico", "Eletrônica",
     ["Curto ao terra na linha de 5V", "Sensor em curto puxando a referência"]),
    ("P0643", "Tensão de referência dos sensores A — alta", "critico", "Eletrônica",
     ["Curto ao positivo na linha de referência"]),
    ("P0650", "Lâmpada de injeção (MIL) — circuito de controle", "informativo", "Eletrônica",
     ["Lâmpada queimada", "Fiação do painel com falha"]),
    ("P0685", "Relé de alimentação do ECM — circuito", "critico", "Eletrônica",
     ["Relé principal defeituoso", "Fiação com falha"]),
    ("P0686", "Relé de alimentação do ECM — sinal baixo", "critico", "Eletrônica",
     ["Curto ao terra"]),
    ("P0687", "Relé de alimentação do ECM — sinal alto", "critico", "Eletrônica",
     ["Curto ao positivo"]),
    # ── ECM / módulos ─────────────────────────────────────────────
    ("P0600", "Comunicação serial do módulo — falha", "atencao", "Eletrônica",
     ["Fiação de comunicação com falha", "Módulo defeituoso"]),
    ("P0601", "ECM/PCM — erro de checksum na memória interna", "critico", "Eletrônica",
     ["Módulo com falha interna", "Reprogramação necessária"]),
    ("P0602", "ECM/PCM — erro de programação", "critico", "Eletrônica",
     ["Programação incompleta ou corrompida"]),
    ("P0603", "ECM/PCM — falha na memória KAM", "atencao", "Eletrônica",
     ["Bateria desconectada com frequência", "Alimentação de memória interrompida",
      "Módulo com falha"]),
    ("P0604", "ECM/PCM — falha na memória RAM", "critico", "Eletrônica",
     ["Módulo com falha interna"]),
    ("P0605", "ECM/PCM — falha na memória ROM", "critico", "Eletrônica",
     ["Módulo com falha interna"]),
    ("P0606", "ECM/PCM — falha no processador", "critico", "Eletrônica",
     ["Módulo com falha interna"]),
    ("P0607", "Módulo de controle — desempenho anormal", "atencao", "Eletrônica",
     ["Alimentação/terra do módulo com mau contato", "Módulo com falha"]),
    ("P0630", "VIN não programado ou incompatível — ECM/PCM", "atencao", "Eletrônica",
     ["Módulo substituído sem programação do VIN"]),
    # ── Transmissão (complementa famílias) ────────────────────────
    ("P0729", "Relação de marcha incorreta — 6ª marcha", "critico", "Transmissão",
     ["Solenoides de troca com falha", "Embreagens internas desgastadas", "Fluido degradado"]),
    ("P0741", "Solenóide do conversor de torque — emperrado aberto", "critico", "Transmissão",
     ["Solenóide TCC defeituoso", "Fluido de transmissão degradado"]),
    ("P0780", "Falha genérica de troca de marcha", "critico", "Transmissão",
     ["Solenoides com falha", "Pressão hidráulica fora da faixa"]),
    ("P0781", "Troca 1ª–2ª — falha", "critico", "Transmissão",
     ["Solenóide de troca com falha", "Fluido degradado"]),
    ("P0782", "Troca 2ª–3ª — falha", "critico", "Transmissão",
     ["Solenóide de troca com falha"]),
    ("P0783", "Troca 3ª–4ª — falha", "critico", "Transmissão",
     ["Solenóide de troca com falha"]),
    ("P0784", "Troca 4ª–5ª — falha", "critico", "Transmissão",
     ["Solenóide de troca com falha"]),
    ("P0868", "Pressão do fluido da transmissão — baixa", "critico", "Transmissão",
     ["Nível de fluido baixo", "Bomba da transmissão desgastada"]),
    # ── P2xxx: borboleta eletrônica / mistura / diversos ──────────
    ("P2096", "Ajuste pós-catalisador muito pobre — banco 1", "atencao", "Emissões",
     ["Vazamento no escapamento", "Sonda pós-catalisador imprecisa", "Mistura pobre real"]),
    ("P2097", "Ajuste pós-catalisador muito rico — banco 1", "atencao", "Emissões",
     ["Sonda pós-catalisador imprecisa", "Mistura rica real"]),
    ("P2098", "Ajuste pós-catalisador muito pobre — banco 2", "atencao", "Emissões",
     ["Vazamento no escapamento no banco 2"]),
    ("P2099", "Ajuste pós-catalisador muito rico — banco 2", "atencao", "Emissões",
     ["Sonda pós-catalisador imprecisa"]),
    ("P2100", "Atuador da borboleta eletrônica — circuito aberto", "critico", "Motor",
     ["Motor do corpo de borboleta defeituoso", "Fiação com falha"]),
    ("P2101", "Atuador da borboleta eletrônica — faixa/desempenho", "critico", "Motor",
     ["Corpo de borboleta sujo ou travado", "Engrenagem interna desgastada"]),
    ("P2102", "Atuador da borboleta eletrônica — corrente baixa", "critico", "Motor",
     ["Circuito aberto no motor da borboleta"]),
    ("P2103", "Atuador da borboleta eletrônica — corrente alta", "critico", "Motor",
     ["Borboleta travada", "Curto no circuito do motor"]),
    ("P2104", "Borboleta eletrônica — marcha lenta forçada", "atencao", "Motor",
     ["Falha em sensor da borboleta/pedal (ver DTCs associados)"]),
    ("P2105", "Borboleta eletrônica — desligamento forçado do motor", "critico", "Motor",
     ["Falha múltipla no sistema ETC (ver DTCs associados)"]),
    ("P2106", "Borboleta eletrônica — potência limitada", "atencao", "Motor",
     ["Falha em sensor do sistema ETC (ver DTCs associados)"]),
    ("P2107", "Módulo da borboleta eletrônica — processador", "critico", "Motor",
     ["Módulo ETC com falha interna"]),
    ("P2108", "Módulo da borboleta eletrônica — desempenho", "critico", "Motor",
     ["Módulo ETC com falha"]),
    ("P2110", "Borboleta eletrônica — RPM limitado", "atencao", "Motor",
     ["Falha no sistema ETC (ver DTCs associados)"]),
    ("P2111", "Borboleta eletrônica — travada aberta", "critico", "Motor",
     ["Corpo de borboleta com detritos", "Mola de retorno com falha"]),
    ("P2112", "Borboleta eletrônica — travada fechada", "critico", "Motor",
     ["Corpo de borboleta sujo ou travado"]),
    ("P2118", "Motor da borboleta — corrente fora da faixa", "critico", "Motor",
     ["Motor da borboleta desgastado", "Alimentação com mau contato"]),
    ("P2119", "Corpo de borboleta — faixa/desempenho", "atencao", "Motor",
     ["Corpo de borboleta sujo", "Posição de repouso fora do aprendizado"]),
    ("P2122", "Sensor do pedal D — sinal baixo", "critico", "Motor",
     ["Curto ao terra no circuito do pedal", "Sensor do pedal defeituoso"]),
    ("P2123", "Sensor do pedal D — sinal alto", "critico", "Motor",
     ["Circuito aberto no pedal", "Sensor defeituoso"]),
    ("P2127", "Sensor do pedal E — sinal baixo", "critico", "Motor",
     ["Curto ao terra no circuito do pedal"]),
    ("P2128", "Sensor do pedal E — sinal alto", "critico", "Motor",
     ["Circuito aberto no pedal"]),
    ("P2135", "Correlação entre sensores da borboleta A/B", "critico", "Motor",
     ["Sensor TPS defeituoso", "Conector com mau contato", "Corpo de borboleta com falha"]),
    ("P2138", "Correlação entre sensores do pedal D/E", "critico", "Motor",
     ["Sensor do pedal defeituoso", "Conector com mau contato"]),
    ("P2177", "Mistura muito pobre fora da marcha lenta — banco 1", "atencao", "Motor/Emissões",
     ["Vazamento de vácuo", "Injetores restritos", "Pressão de combustível baixa"]),
    ("P2178", "Mistura muito rica fora da marcha lenta — banco 1", "atencao", "Motor/Emissões",
     ["Injetor vazando", "Pressão de combustível alta", "Sensor MAF impreciso"]),
    ("P2179", "Mistura muito pobre fora da marcha lenta — banco 2", "atencao", "Motor/Emissões",
     ["Vazamento de vácuo no banco 2"]),
    ("P2180", "Mistura muito rica fora da marcha lenta — banco 2", "atencao", "Motor/Emissões",
     ["Injetor do banco 2 vazando"]),
    ("P2181", "Sistema de arrefecimento — desempenho", "atencao", "Arrefecimento",
     ["Termostato com falha", "Sensor ECT impreciso", "Nível de arrefecimento baixo"]),
    ("P2187", "Mistura muito pobre em marcha lenta — banco 1", "atencao", "Motor/Emissões",
     ["Vazamento de vácuo", "Válvula PCV com falha", "Injetores sujos"]),
    ("P2188", "Mistura muito rica em marcha lenta — banco 1", "atencao", "Motor/Emissões",
     ["Injetor vazando", "Regulador de pressão com falha"]),
    ("P2189", "Mistura muito pobre em marcha lenta — banco 2", "atencao", "Motor/Emissões",
     ["Vazamento de vácuo no banco 2"]),
    ("P2190", "Mistura muito rica em marcha lenta — banco 2", "atencao", "Motor/Emissões",
     ["Injetor do banco 2 vazando"]),
    ("P2195", "Sonda lambda B1S1 — sinal preso em pobre", "atencao", "Emissões",
     ["Vazamento de vácuo/escape", "Sonda envelhecida", "Pressão de combustível baixa"]),
    ("P2196", "Sonda lambda B1S1 — sinal preso em rico", "atencao", "Emissões",
     ["Injetor vazando", "Sonda contaminada"]),
    ("P2197", "Sonda lambda B2S1 — sinal preso em pobre", "atencao", "Emissões",
     ["Vazamento de vácuo no banco 2", "Sonda envelhecida"]),
    ("P2198", "Sonda lambda B2S1 — sinal preso em rico", "atencao", "Emissões",
     ["Injetor do banco 2 vazando"]),
    ("P2263", "Sistema turbo — desempenho de pressão", "atencao", "Motor",
     ["Vazamento entre turbo e coletor", "Geometria variável travada", "Intercooler vazando"]),
    ("P2270", "Sonda lambda B1S2 — sinal preso em pobre", "informativo", "Emissões",
     ["Vazamento no escapamento", "Sonda envelhecida"]),
    ("P2271", "Sonda lambda B1S2 — sinal preso em rico", "informativo", "Emissões",
     ["Sonda contaminada"]),
    ("P2272", "Sonda lambda B2S2 — sinal preso em pobre", "informativo", "Emissões",
     ["Vazamento no escapamento no banco 2"]),
    ("P2273", "Sonda lambda B2S2 — sinal preso em rico", "informativo", "Emissões",
     ["Sonda contaminada"]),
    ("P2279", "Vazamento no sistema de admissão", "atencao", "Motor",
     ["Junta do coletor vazando", "Mangueira de vácuo solta", "Corpo de borboleta mal vedado"]),
    ("P2299", "Pedal do freio e do acelerador acionados juntos — incompatibilidade", "atencao",
     "Motor",
     ["Interruptor do freio desregulado", "Condução com dois pés"]),
    ("P2401", "Bomba de detecção de vazamento EVAP — circuito baixo", "informativo", "Emissões",
     ["Curto ao terra no circuito da bomba"]),
    ("P2402", "Bomba de detecção de vazamento EVAP — circuito alto", "informativo", "Emissões",
     ["Circuito aberto"]),
    ("P2404", "Bomba de detecção de vazamento EVAP — faixa/desempenho", "informativo", "Emissões",
     ["Bomba de detecção defeituosa", "Mangueira obstruída"]),
    ("P2413", "Sistema EGR — desempenho", "atencao", "Emissões",
     ["Passagens EGR obstruídas por carbono", "Válvula EGR desgastada"]),
    ("P2440", "Válvula de ar secundário travada aberta — banco 1", "atencao", "Emissões",
     ["Válvula comutadora travada", "Corrosão por condensação"]),
    ("P2502", "Sistema de carga — tensão fora da faixa", "atencao", "Elétrica",
     ["Alternador com falha", "Regulador de tensão defeituoso"]),
    ("P2503", "Sistema de carga — tensão baixa", "atencao", "Elétrica",
     ["Alternador fraco", "Correia patinando", "Bateria em fim de vida"]),
    ("P2504", "Sistema de carga — tensão alta", "atencao", "Elétrica",
     ["Regulador de tensão com falha"]),
    ("P2610", "ECM/PCM — temporizador interno de desligamento", "atencao", "Eletrônica",
     ["Módulo com falha interna", "Alimentação permanente interrompida"]),
    # ── U0xxx: barramento ─────────────────────────────────────────
    ("U0002", "Barramento CAN de alta velocidade — desempenho", "critico", "Rede/Eletrônica",
     ["Resistor de terminação com falha", "Fiação CAN degradada"]),
    ("U0003", "Barramento CAN de alta velocidade — CAN High aberto", "critico", "Rede/Eletrônica",
     ["Fio CAN High rompido", "Conector com pino recuado"]),
    ("U0004", "Barramento CAN de alta velocidade — CAN Low aberto", "critico", "Rede/Eletrônica",
     ["Fio CAN Low rompido"]),
    ("U0007", "Barramento CAN de alta velocidade — CAN Low em curto com o terra", "critico",
     "Rede/Eletrônica",
     ["Chicote danificado encostando na carroceria"]),
    ("U0009", "Barramento CAN de alta velocidade — CAN Low em curto com CAN High", "critico",
     "Rede/Eletrônica",
     ["Chicote CAN esmagado ou derretido"]),
    ("U0300", "Incompatibilidade de software entre módulos", "atencao", "Rede/Eletrônica",
     ["Módulo substituído com software incompatível", "Atualização incompleta"]),
    ("U0401", "Dados inválidos recebidos do ECM/PCM", "critico", "Rede/Eletrônica",
     ["ECM com falha interna", "Barramento CAN com interferência"]),
    ("U0402", "Dados inválidos recebidos do TCM", "critico", "Rede/Eletrônica",
     ["TCM com falha", "Barramento CAN com interferência"]),
    ("U0415", "Dados inválidos recebidos do módulo ABS", "critico", "Rede/Eletrônica",
     ["Módulo ABS com falha", "Sensor de roda enviando dado implausível"]),
    ("U0422", "Dados inválidos recebidos do BCM", "atencao", "Rede/Eletrônica",
     ["BCM com falha", "Barramento com interferência"]),
    ("U0423", "Dados inválidos recebidos do painel de instrumentos", "informativo",
     "Rede/Eletrônica",
     ["Painel com falha"]),
)

_MISFIRE_CAUSES = [
    "Vela do cilindro desgastada ou incorreta",
    "Bobina/cabo de ignição com falha",
    "Injetor entupido ou vazando",
    "Compressão baixa no cilindro",
]


def _fmt(base: str, offset: int) -> str:
    # A numeração dos DTCs genéricos é decimal: P0309 + 1 = P0310, não P030A.
    prefix, num = base[0], int(base[1:], 10)
    return f"{prefix}{num + offset:04d}"


@lru_cache(maxsize=1)
def build_catalog() -> dict[str, DTCInfo]:
    db: dict[str, DTCInfo] = {}

    def add(code: str, desc: str, sev: str, system: str, causes: list[str]) -> None:
        db[code] = DTCInfo(code, desc, sev, system, causes)

    for base, count, comp, system, sev in _QUINTETOS:
        for i in range(count):
            add(_fmt(base, i), f"{comp} — {_Q5[i]}", sev, system, _causes_q5(comp, i))

    for base, bank, sensor in _SONDAS:
        sev = "atencao" if sensor == 1 else "informativo"
        for i, suffix in enumerate(_O2_6):
            causes = (
                [f"Sonda lambda B{bank}S{sensor} defeituosa", "Fiação ou conector com mau contato"]
                if i != 5
                else [
                    "Resistência de aquecimento da sonda queimada",
                    "Fusível do aquecedor queimado",
                ]
            )
            add(_fmt(base, i), f"Sonda lambda B{bank}S{sensor} — {suffix}", sev, "Emissões", causes)

    for base, bank, sensor in _AQUECEDORES:
        label = f"Controle do aquecedor da sonda B{bank}S{sensor}"
        for i, suffix in enumerate(("circuito com falha", "sinal baixo", "sinal alto")):
            add(
                _fmt(base, i),
                f"{label} — {suffix}",
                "informativo",
                "Emissões",
                ["Aquecedor da sonda queimado", "Driver do ECM ou fiação com falha"],
            )

    for cyl in range(1, 13):
        add(
            _fmt("P0201", cyl - 1),
            f"Injetor do cilindro {cyl} — circuito com falha",
            "atencao",
            "Combustível",
            [f"Injetor do cilindro {cyl} defeituoso", "Fiação ou conector com mau contato"],
        )
        base = _fmt("P0261", (cyl - 1) * 3)
        add(base, f"Injetor do cilindro {cyl} — circuito baixo", "atencao", "Combustível",
            ["Curto ao terra no circuito do injetor"])
        add(_fmt(base, 1), f"Injetor do cilindro {cyl} — circuito alto", "atencao", "Combustível",
            ["Circuito aberto ou curto ao positivo"])
        add(_fmt(base, 2), f"Cilindro {cyl} — contribuição/balanceamento fora do esperado",
            "atencao", "Motor", ["Injetor desbalanceado", "Compressão baixa no cilindro"])
        add(
            _fmt("P0301", cyl - 1),
            f"Falha de ignição — cilindro {cyl}",
            "critico",
            "Motor/Ignição",
            list(_MISFIRE_CAUSES),
        )

    for i, letter in enumerate("ABCDEFGHIJKL"):
        add(
            _fmt("P0351", i),
            f"Bobina de ignição {letter} — circuito primário/secundário",
            "atencao",
            "Motor/Ignição",
            [f"Bobina {letter} defeituosa", "Fiação ou conector com mau contato"],
        )

    gears = ("1ª", "2ª", "3ª", "4ª", "5ª", "ré")
    for i, gear in enumerate(gears):
        add(
            _fmt("P0731", i),
            f"Relação de marcha incorreta — {gear}",
            "critico",
            "Transmissão",
            ["Solenoides de troca com falha", "Embreagens internas desgastadas",
             "Fluido degradado"],
        )

    for base, name in _SOLENOIDES:
        for i, suffix in enumerate(_SOL5):
            causes = (
                ["Fiação ou conector com mau contato", f"{name} defeituoso"]
                if i >= 3
                else [f"{name} defeituoso", "Fluido de transmissão degradado ou contaminado"]
            )
            add(_fmt(base, i), f"{name} — {suffix}", "critico", "Transmissão", causes)

    for code, (module, sev) in _MODULOS_REDE.items():
        add(
            code,
            f"Perda de comunicação com {module}",
            sev,
            "Rede/Eletrônica",
            ["Módulo sem alimentação ou terra", "Barramento CAN interrompido até o módulo"],
        )

    for code, desc, sev, system, causes in _EXPLICITOS:
        add(code, desc, sev, system, causes)

    return db


def catalog_size() -> int:
    return len(build_catalog())
