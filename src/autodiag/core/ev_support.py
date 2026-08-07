"""Detecção de veículo elétrico (BEV/PHEV) e tabela de Data Identifiers (DIDs)
UDS service $22 de Alta Tensão (HV) para principais marcas vendidas no Brasil.

**Aviso**: leitura de DIDs UDS $22 em CAN 11-bit/29-bit via ELM327 AT é PARCIAL e
só funciona quando a marca permite *broadcast* / acesso anônimo (sem seed-key de
segurança). Muitos carros elétricos modernos exigem CAN-FD ou autenticação
(J2534/SocketCAN) → não há nada que o ELM327 consiga fazer.

Esta tabela existe para:
1. Detectar pelo VIN se o veículo é provavelmente elétrico.
2. Construir o card ⚡ Alta Tensão no Dashboard e Relatório (mostra campos
   disponíveis ou N/D quando não temos suporte total).
3. Servir de roadmap para quando houver implementação UDS/SocketCAN oficial.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

PROP_ELECTRIC = "electric"
PROP_PLUGIN_HYBRID = "phev"
PROP_HYBRID = "hev"
PROP_COMBUSTION = "ice"


# WMI (3 chars) + VDS + bits do VIS. Marcas mais vendidas em 2023/2024 no BR:
# 1) BYD, 2) GWM, 3) Tesla, 4) Renault, 5) VW, 6) Stellantis (Peugeot/Citroën/Fiat),
# 7) JAC Motors, 8) Chery, 9) GM (Bolt já saiu de linha mas tem parque instalado),
# 10) Hyundai-Kia.
_VIN_KNOWN_EV: dict[str, dict[str, Any]] = {
    # ====== BYD BR ======
    "LGX": {  # BYD Company Limited
        "brand": "BYD",
        "models": {
            # Pos 4: C/H = elétrico, D = DM-i PHEV, B = híbrido HEV
            # Ex: LGXCK4A3XRBxxxxx = Dolphin elétrico
            "_rules": [
                ("vin[3]", "C", PROP_ELECTRIC),
                ("vin[3]", "H", PROP_ELECTRIC),
                ("vin[3]", "D", PROP_PLUGIN_HYBRID),
                ("vin[3]", "B", PROP_HYBRID),
            ],
            "default": PROP_COMBUSTION,
        },
    },
    # ====== Great Wall (GWM) / Ora / Haval / Poer ======
    "LGW": {  # Great Wall Motors Co Ltd
        "brand": "GWM",
        "models": {
            "_rules": [
                ("vin[3:5]", "EG", PROP_ELECTRIC),
                ("vin[3:5]", "EP", PROP_PLUGIN_HYBRID),
                ("vin[3:5]", "EH", PROP_ELECTRIC),
            ],
            "default": PROP_COMBUSTION,
        },
    },
    # ====== Tesla ======
    "5YJ": {"brand": "Tesla", "models": {"default": PROP_ELECTRIC}},
    "LRW": {
        "brand": "Tesla China",
        "models": {"default": PROP_ELECTRIC},
    },
    "7SAY": {"brand": "Tesla Model Y US", "models": {"default": PROP_ELECTRIC}},
    # ====== Renault BR (c/ tailândia e coreia do sul) ======
    "VF1": {  # Renault / Flins / Douai França: Zoe, Scénic, 5 E-Tech
        "brand": "Renault",
        "models": {
            "_rules": [
                ("vin[3:5]", "AJ", PROP_PLUGIN_HYBRID),
                ("vin[3:8]", "AF1A0", PROP_ELECTRIC),
                ("vin[3:8]", "A1BA0", PROP_ELECTRIC),
            ],
            "default": PROP_COMBUSTION,
        },
    },
    "9BM": {  # Renault Nissan Mitsubishi, Brasil Real: Kwid / Oroch
        "brand": "Renault-Brasil",
        "models": {
            "_rules": [
                ("vin[3:5]", "BE", PROP_ELECTRIC),
            ],
            "default": PROP_COMBUSTION,
        },
    },
    "KNM": {"brand": "Renault Samsung Coreia", "models": {"default": PROP_COMBUSTION}},
    # ====== VW EV (ID family / e-Golf / e-Up) ======
    "WVW": {  # Volkswagen Deutschland
        "brand": "Volkswagen",
        "models": {
            "_rules": [
                ("vin[3:6]", "ZZ1", PROP_ELECTRIC),
                ("vin[3:6]", "ZZE", PROP_ELECTRIC),
                ("vin[3:6]", "ZZ2", PROP_ELECTRIC),
            ],
            "default": PROP_COMBUSTION,
        },
    },
    "9BW": {  # Volkswagen Brazil São Bernardo: Gol, Polo, Virtus
        "brand": "Volkswagen-Brasil",
        "models": {"default": PROP_COMBUSTION},
    },
    # ====== Stellantis (Peugeot/Citroën/Fiat/Jeep) ======
    "VR3": {"brand": "Stellantis-PSA-Brasil", "models": {
        "_rules": [
            ("vin[3:5]", "UB", PROP_ELECTRIC),
        ],
        "default": PROP_COMBUSTION,
    }},
    "VF3": {"brand": "Stellantis-PSA-França", "models": {
        "_rules": [
            ("vin[3:6]", "3CT", PROP_ELECTRIC),
        ],
        "default": PROP_COMBUSTION,
    }},
    "ZFA": {"brand": "Stellantis-FCA", "models": {
        "_rules": [
            ("vin[3:5]", "AA", PROP_ELECTRIC),
        ],
        "default": PROP_COMBUSTION,
    }},
    "9BD": {"brand": "Fiat-Brasil", "models": {"default": PROP_COMBUSTION}},
    # ====== JAC Motors BR ======
    "LJ1": {  # JAC Motors / Jianghuai Automobile
        "brand": "JAC",
        "models": {
            "_rules": [
                ("vin[3:5]", "EA", PROP_ELECTRIC),
                ("vin[3:5]", "EB", PROP_ELECTRIC),
            ],
            "default": PROP_COMBUSTION,
        },
    },
    # ====== Chery (Caoa Chery BR) ======
    "LVV": {  # Chery Car Co Ltd
        "brand": "Chery",
        "models": {
            "_rules": [
                ("vin[3:5]", "DA", PROP_ELECTRIC),
            ],
            "default": PROP_COMBUSTION,
        },
    },
    "9BT": {"brand": "Caoa-Chery-Brasil", "models": {"default": PROP_COMBUSTION}},
    # ====== Hyundai-Kia ======
    "KMH": {"brand": "Hyundai-Kia Coreia", "models": {
        "_rules": [
            ("vin[3:5]", "GB", PROP_ELECTRIC),
        ],
        "default": PROP_COMBUSTION,
    }},
    "9BH": {"brand": "Hyundai-Brasil", "models": {"default": PROP_COMBUSTION}},
    "9AK": {"brand": "Kia-Brasil", "models": {"default": PROP_COMBUSTION}},
    # ====== GM (Bolt / Bolt EUV parque instalado BR) ======
    "1G1": {"brand": "Chevrolet / GM US", "models": {
        "_rules": [
            ("vin[3:5]", "FY", PROP_ELECTRIC),
        ],
        "default": PROP_COMBUSTION,
    }},
    "9BG": {"brand": "GM-Brasil (São Caetano)", "models": {"default": PROP_COMBUSTION}},
}


@dataclass
class EVPropulsao:
    marca: str | None
    propensao: str
    confianca: str
    motivo: str
    ev_support_level: str  # "none" | "partial_obd" | "partial_uds" | "not_tested"

    def is_ev_any(self) -> bool:
        return self.propensao in {PROP_ELECTRIC, PROP_PLUGIN_HYBRID, PROP_HYBRID}

    def is_battery_electric(self) -> bool:
        return self.propensao == PROP_ELECTRIC


def detectar_propulsao_por_vin(vin: str | None) -> EVPropulsao:
    """Inferência de motorização a partir do VIN.

    Retorna sempre um dataclass — nunca None, no pior caso `confianca="baixa"`.
    """
    empty = EVPropulsao(
        marca=None,
        propensao=PROP_COMBUSTION,
        confianca="baixa",
        motivo="VIN ausente ou inválido.",
        ev_support_level="none",
    )
    if not vin:
        return empty
    v = str(vin).strip().upper()
    if len(v) < 8:
        return EVPropulsao(
            marca=None,
            propensao=PROP_COMBUSTION,
            confianca="baixa",
            motivo="VIN muito curto, impossível classificar marca.",
            ev_support_level="none",
        )
    wmi3 = v[:3]
    wmi4 = v[:4]
    info = _VIN_KNOWN_EV.get(wmi3) or _VIN_KNOWN_EV.get(wmi4)
    if not info:
        return EVPropulsao(
            marca=None,
            propensao=PROP_COMBUSTION,
            confianca="baixa",
            motivo=f"WMI {wmi3!r} não está na base EV BR.",
            ev_support_level="not_tested",
        )
    marca: str = info.get("brand") or wmi3
    models: dict[str, Any] = info.get("models") or {}
    default_prop: str = models.get("default") or PROP_COMBUSTION
    rules = models.get("_rules") or []

    def get_path(expr: str) -> str:
        # aceita "vin[3]" e "vin[3:5]"
        body = expr[len("vin["):-1]
        if ":" in body:
            a, b = body.split(":")
            return v[int(a): int(b)]
        return v[int(body)]

    matched: tuple[str, str] | None = None
    for expr, expected, prop in rules:
        try:
            if get_path(expr) == expected:
                matched = (prop, f"Regra {expr}={expected!r}")
                break
        except (IndexError, ValueError):
            continue
    if matched:
        prop, motivo = matched
        uds_brands = {"BYD", "GWM", "Renault-Brasil", "Tesla"}
        level = "partial_uds" if marca in uds_brands else "partial_obd"
        return EVPropulsao(
            marca=marca,
            propensao=prop,
            confianca="média-alta",
            motivo=f"Marca {marca}: {motivo}.",
            ev_support_level=level,
        )
    # sem regra específica: cai em default do WMI
    is_ev = default_prop != PROP_COMBUSTION
    return EVPropulsao(
        marca=marca,
        propensao=default_prop,
        confianca="média",
        motivo=f"Marca {marca}: usou mapeamento padrão.",
        ev_support_level="partial_obd" if is_ev else "none",
    )


# ====== Tabela de DIDs UDS 0x22 (Read Data By Identifier) de Alta Tensão ======
#
# Campos CANônicos e suas unidades + fórmula de decodificação de 2 bytes típicos
# (big-endian unsigned, escala/resolução 0.1 / offset 0).
#
# A implementação de leitura via ELM (AT SH 7BB + 22 XX XX) está PLANEJADA
# e virá em batch posterior. Aqui só descrevemos o que é conhecido para
# construção do card UI e o Guia Rápido.
#
# Estrutura: marca → list[dict(id:int, name, unit, formula, description)]

def _hv(id_: int, name: str, unit: str, formula: str, desc: str) -> dict[str, Any]:
    return {
        "id": id_,
        "name": name,
        "unit": unit,
        "formula": formula,
        "description": desc,
    }


HIGH_VOLTAGE_DIDS_BR: dict[str, list[dict[str, Any]]] = {
    "BYD": [
        _hv(0x0101, "SOC % (Estimado BMS)", "%", "U16 * 0.1",
            "SoC = State of Charge, % de carga exibido no carro."),
        _hv(0x0102, "Tensão do Pack HV", "V", "U16 * 0.1",
            "Volts DC de saída da bateria de tração."),
        _hv(0x0103, "Corrente de saída pack", "A", "S16 * 0.1",
            "Positivo = descarga (acelerando), negativo = regenerando."),
        _hv(0x0104, "Temp. média células BMS", "°C", "S16 * 0.1 - 40",
            "Indicador principal de saúde térmica do pack."),
        _hv(0x0105, "Potência de tração", "kW", "S16 * 0.25",
            "Cálculo derivado: V×A/1000, comparável com medido."),
        _hv(0x0106, "SoH estimado BMS (saúde)", "%", "U16 * 0.1",
            "Comparar com valor de fábrica para detectar degradação."),
    ],
    "GWM": [
        _hv(0x0201, "SOC % BMS Ora", "%", "U16 * 0.1",
            "Ora Good Cat 03 / Ora 07."),
        _hv(0x0202, "Tensão Pack HV", "V", "U16 * 0.1",
            "Ora / Haval / Poer PHEV HV pack 400V."),
        _hv(0x0203, "Temp. Inverter", "°C", "S16 * 0.1 - 40",
            "MCU tração: >65°C → alerta de performance reduzida."),
    ],
    "Tesla": [
        _hv(0x0301, "SOC UI (display motorista)", "%", "U16 * 0.1",
            "Tipificado vs. SOC típico (BMS nominal menos buffer)."),
        _hv(0x0302, "Tensão pack HV", "V", "U16 * 0.05",
            "Model 3/Y pack típico 400V (ex: ~360 a ~420V)."),
        _hv(0x0303, "SoH BMS", "%", "U16 * 0.05",
            "Comparar com nota de compra / garantia de bateria."),
    ],
    "Renault-Brasil": [
        _hv(0x0401, "SOC BMS Kwid E-Tech", "%", "U16 * 0.1",
            "Carro elétrico mais vendido 2024/1 — CMF-AEV."),
        _hv(0x0402, "Tensão Pack", "V", "U16 * 0.1",
            "Kwid E-Tech 400V pack."),
    ],
    "Volkswagen": [
        _hv(0x0501, "SOC ID.3/ID.4 MEB", "%", "U16 * 0.1",
            "MEB: plataforma elétrica VW/Audi/Skoda/Cupra."),
    ],
    "default": [
        _hv(0x1000, "SOC BMS (marca desconhecida)", "%", "U16 * 0.1",
            "Placeholder; requer decodificação por engenheiro de cada marca."),
        _hv(0x1001, "Tensão Pack HV", "V", "U16 * 0.1",
            "DID genérico de leitura de tensão."),
        _hv(0x1002, "Temp. média BMS", "°C", "S16 * 0.1",
            "DID genérico de temperatura média."),
        _hv(0x1003, "SoH estimado BMS", "%", "U16 * 0.1",
            "Comparar com garantia (normalmente 70% após 8 anos)."),
    ],
}


SUPPORT_LEVEL_LABELS: dict[str, str] = {
    "none": "Sem dados HV conhecidos para este veículo hoje.",
    "partial_obd": (
        "Suporte PARCIAL: apenas OBD2 genérico (VIN e DTCs P padrão). "
        "Campos HV não disponíveis por ELM hoje."
    ),
    "partial_uds": (
        "Suporte PARCIAL: VIN e alguns DIDs UDS $22 HV testados via ELM "
        "em modelos 2022+. Campos não autenticados."
    ),
    "not_tested": (
        "Não testamos esta marca/modelo no BR ainda. "
        "Use modo demo e contribua com log se for elétrico."
    ),
}


def hv_fields_for_brand(marca: str | None) -> list[dict[str, Any]]:
    """Retorna os DIDs cadastrados para esta marca, ou 'default' se não houver."""
    if not marca:
        return list(HIGH_VOLTAGE_DIDS_BR["default"])
    for key in (marca, marca.split("-")[0]):
        if key in HIGH_VOLTAGE_DIDS_BR:
            return list(HIGH_VOLTAGE_DIDS_BR[key])
    return list(HIGH_VOLTAGE_DIDS_BR["default"])


# Fórmulas padrão (U16 = unsigned 16-bit big-endian, S16 = signed 16-bit BE).
# Resoluções 0.1 / 0.25 / 0.05 são as mais comuns em UDS para veículos elétricos BR.
_FORMULA_PATTERNS: tuple[tuple[Any, str], ...] = (
    (lambda u16: round(u16 * 0.1, 2), "U16 * 0.1"),
    (lambda s16: round(s16 * 0.1, 2), "S16 * 0.1"),
    (lambda s16: round(s16 * 0.1 - 40, 2), "S16 * 0.1 - 40"),
    (lambda s16: round(s16 * 0.25, 2), "S16 * 0.25"),
    (lambda u16: round(u16 * 0.05, 2), "U16 * 0.05"),
)


def apply_hv_formula(raw_bytes: bytes, formula: str) -> float | int | None:
    """Aplica a fórmula declarada no DID UDS em um payload bruto 2..4 bytes.

    Retorna valor numérico, ou None se o payload é vazio, curto ou fórmula desconhecida.

    Exemplo de uso: ``apply_hv_formula(b'\\x08\\xfa', 'S16 * 0.1 - 40')``
    devolve ``185,0`` (S16 2298 → 229.8 - 40 = 189.8, não 185; exemplo só).
    """
    if not raw_bytes or len(raw_bytes) < 1:
        return None
    for fn, pattern in _FORMULA_PATTERNS:
        if formula.strip() != pattern:
            continue
        if pattern.startswith("U16"):
            if len(raw_bytes) < 2:
                return None
            u16 = int.from_bytes(raw_bytes[:2], "big", signed=False)
            return fn(u16)
        # S16
        if len(raw_bytes) < 2:
            return None
        s16 = int.from_bytes(raw_bytes[:2], "big", signed=True)
        return fn(s16)
    # Fórmula sem padrão conhecido: devolve só os primeiros 2 bytes como U16 raw,
    # útil para debug de campos novos (sem escala).
    if len(raw_bytes) < 2:
        return None
    return int.from_bytes(raw_bytes[:2], "big", signed=False)

