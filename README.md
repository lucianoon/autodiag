# AutoDiag

Ferramenta de diagnostico OBD2 para veiculos 2015+, com leitura de DTCs,
PIDs ao vivo, historico local e interface web para acompanhamento do scan.

## Funcionalidades

- Leitura de codigos DTC via adaptador ELM327.
- Consulta local de codigos e severidade.
- Coleta de PIDs ao vivo como RPM, velocidade, temperatura e MAF.
- Historico local de diagnosticos.
- Interface CLI e servidor web com FastAPI.
- Analise assistida por IA quando `ANTHROPIC_API_KEY` esta configurada.

## Tecnologias

- Python 3.11+
- FastAPI
- PySerial
- Rich
- SQLite

## Como executar

```bash
uv sync
uv run autodiag scan --no-ai
uv run autodiag serve
```

## Observacao

Projeto organizado como parte de portfolio tecnico, representando uma solucao
de diagnostico automotivo com integracao OBD2, API local e interface web.
