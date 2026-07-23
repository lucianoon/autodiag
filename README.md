# AutoDiag

[![CI](https://github.com/lucianoon/autodiag/actions/workflows/ci.yml/badge.svg)](https://github.com/lucianoon/autodiag/actions/workflows/ci.yml)
[![Licença: MIT](https://img.shields.io/badge/licen%C3%A7a-MIT-green.svg)](LICENSE)

Ferramenta de diagnóstico OBD2 em Python para veículos 2015+ usando adaptadores
**ELM327** (USB, Bluetooth serial ou Wi-Fi). Lê códigos de falha (DTCs), coleta
PIDs ao vivo, identifica o veículo pelo VIN, guarda o histórico em SQLite e
oferece uma interface web local com acompanhamento do scan em tempo real.

## O que ela faz hoje

- **Leitura de DTCs** (modo 03) via ELM327, com decodificação dos códigos
  P/C/B/U e consulta a uma base local com ~65 códigos comuns (descrição em
  português, severidade, sistema e causas prováveis).
- **Limpeza de DTCs** (modo 04), com confirmação.
- **PIDs ao vivo** (modo 01): RPM, velocidade, temperatura do motor e da
  admissão, posição da borboleta, MAF, fuel trim curto/longo B1, tensão da
  sonda O2 B1S1 e nível de combustível.
- **Identificação do veículo**: leitura do VIN (modo 09 02), decodificação
  local (WMI + ano-modelo) e enriquecimento opcional pela API pública da
  NHTSA (vPIC).
- **Heurística de urgência** (`critico` / `atencao` / `informativo`) baseada
  nos DTCs encontrados e em limites de PIDs (superaquecimento, fuel trim alto,
  MAF baixo).
- **Análise opcional com IA** (Claude, via SDK da Anthropic) quando a variável
  `ANTHROPIC_API_KEY` está definida — pode ser desativada com `--no-ai`.
- **Histórico local** em SQLite (`~/.autodiag/history.db`) com listagem e
  resumo estatístico (total, críticos, DTCs mais frequentes).
- **Interface web** (FastAPI + uvicorn) com página única e streaming do scan
  via Server-Sent Events, além de API JSON para histórico e consulta de DTCs.

## Arquitetura

```
src/autodiag/
├── cli.py              # CLI (argparse): scan, history, summary, dtc, clear, serve
├── core/
│   ├── dtc.py          # Base local de DTCs (DTCInfo, lookup, severidade)
│   └── vehicle.py      # Decodificação de VIN (local + API NHTSA)
├── elm327/
│   └── reader.py       # Comunicação ELM327 (serial/Wi-Fi), decodificação de DTCs e PIDs
├── agents/
│   └── diagnostic.py   # Análise assistida por IA (Anthropic)
├── db/
│   └── history.py      # Histórico de diagnósticos em SQLite
├── ui/
│   └── display.py      # Saída no terminal (rich): tabelas, painéis, status
└── web/
    ├── server.py       # FastAPI: página web, API JSON e stream SSE do scan
    └── static/         # index.html da interface web
```

## Instalação

Requer Python 3.11+ e [uv](https://docs.astral.sh/uv/):

```bash
git clone https://github.com/lucianoon/autodiag.git
cd autodiag
uv sync
```

Para usar a análise com IA (opcional), copie `.env.example` para `.env` e
defina `ANTHROPIC_API_KEY` (também é lido de `~/.autodiag/.env`).

## Uso

Com um adaptador ELM327 conectado ao veículo:

```bash
# Diagnóstico completo (detecta a porta automaticamente em macOS/Linux)
uv run autodiag scan

# Porta específica ou adaptador Wi-Fi
uv run autodiag scan --port /dev/cu.usbserial-1410
uv run autodiag scan --wifi 192.168.0.10

# Sem análise de IA
uv run autodiag scan --no-ai

# Apagar DTCs do veículo (pede confirmação)
uv run autodiag clear
```

Sem hardware, ainda funcionam:

```bash
# Consultar um código na base local
uv run autodiag dtc P0171

# Histórico e estatísticas dos diagnósticos salvos
uv run autodiag history --limit 20
uv run autodiag summary

# Interface web em http://localhost:8000
uv run autodiag serve --open
```

Observação: a detecção automática de porta procura dispositivos `/dev/cu.*`
(macOS). Em Linux/Windows, informe a porta com `--port` (ex.: `COM3`).

## Testes

Os testes cobrem a lógica pura (decodificação de DTCs e PIDs com um reader
falso, VIN, heurística de urgência e histórico com banco temporário) e não
exigem hardware nem chaves de API:

```bash
uv sync
uv run pytest
```

A suíte roda em CI (GitHub Actions, Ubuntu, Python 3.12) a cada push e pull
request.

## Licença

[MIT](LICENSE) — © 2026 Luciano de Oliveira Nunes.
