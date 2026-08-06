# Contribuindo com o AutoDiag

Obrigado pelo interesse! Contribuições de todo tipo são bem-vindas — de
relatos de compatibilidade com veículos (a mais valiosa e a que não exige
escrever código) a novos códigos DTC, correções e features.

## A contribuição mais valiosa: relato de compatibilidade

O AutoDiag precisa de gente testando em carros reais. Se você rodou um scan
em qualquer veículo, [abra um relato de compatibilidade](../../issues/new?template=compatibilidade.yml)
— leva 2 minutos e alimenta a [matriz de compatibilidade](docs/compatibilidade.md).
Funcionou ou não, o relato tem o mesmo valor.

## Preparando o ambiente

Requisitos: Python 3.11+ e [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/lucianoon/autodiag.git
cd autodiag
uv sync --locked
uv run pytest -q         # a suíte inteira roda offline, sem hardware
uv run ruff check .
uv run mypy
```

Sem adaptador ELM327? Sem problema: `uv run autodiag scan --demo` executa o
fluxo completo com um veículo simulado, e os testes usam o mesmo simulador.

## Regras do jogo

- **Testes acompanham código.** Toda mudança de comportamento vem com teste;
  a CI roda pytest + ruff + mypy em Ubuntu e Windows e bloqueia regressão.
- **Offline por padrão.** Testes não podem depender de rede, hardware ou
  chave de API. O adaptador simulado (`elm327/sim.py`) existe para isso.
- **PT-BR nas strings voltadas ao usuário** (descrições de DTC, painéis,
  laudo); código e identificadores em inglês.
- **Commits pequenos e descritivos**, estilo imperativo
  (`feat: ...`, `fix: ...`, `docs: ...`), explicando o porquê no corpo
  quando não for óbvio.
- **DTCs novos**: códigos de famílias padronizadas SAE vão em
  `core/dtc_catalog.py` (tabelas geradoras); descrições revisadas à mão com
  causas específicas vão em `core/dtc.py` (têm precedência). Cite a fonte da
  descrição no PR.

## Por onde começar

Procure as issues marcadas com
[`good first issue`](../../issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22)
— cada uma descreve contexto, arquivos envolvidos e critério de pronto.
Dúvidas? Abra uma [Discussion](../../discussions).

## Segurança

Vulnerabilidades: siga a [política de segurança](SECURITY.md) — reporte de
forma privada, não em issue pública.
