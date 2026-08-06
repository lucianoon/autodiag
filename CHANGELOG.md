# Changelog

Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/);
versionamento segue [SemVer](https://semver.org/lang/pt-BR/).

## [Não publicado]

### Adicionado

- **Branding do relatório** (módulo `core/config.py`, arquivos em
  `~/.autodiag/config.json`): 7 campos personalizáveis (nome oficina, mecânico,
  telefone, e-mail, endereço, URL logo, header da seção de notas), com
  endpoints `GET /api/branding` + `PUT /api/branding` e modal ⚙ **Branding**
  na UI web. Bloco de cabeçalho estilo GitHub Dark renderizado no topo do
  relatório HTML.
- **Notas e Tags editáveis por atendimento**: novo campo `tags: list[str]` no
  dataclass `Session`, migração incremental (`ALTER TABLE ADD COLUMN`),
  `History.update_session(sid, notes=, tags=)` com PATCH parcial, endpoint
  `PATCH /api/session/{sid}`, modal ✎ de edição na UI, preview de tags (≤3
  badges info) + notes truncada em 48 chars no Histórico, painel no Dashboard.
  Coluna `tags` adicionada ao CSV export (UTF-8 BOM para Excel).
- **Onboarding por persona**: modal ❔ **Guia rápido** na navbar, 3 cards de
  perfil (oficina / vistoriador seminovos / entusiasta) com casos de uso,
  abre automaticamente no primeiro acesso quando `GET /api/history?limit=1`
  retorna vazio.
- **Freeze Frame Modo 02 OBD2**: dataclass `FreezeFrame`, parser por PID e
  tamanho (1B / 2B / 4B para DTC) dos 11 PIDs mais úteis (RPM, coolant,
  speed, engine load, throttle, MAF, fuel trims curto/longo B1, O2 B1S1,
  intake temp, mileage), helper `_decode_single_dtc`, implementação demo no
  `SimulatedELM327` (P0171 clássico), evento SSE `freeze_frame` emitido no
  `GET /api/scan/stream`, coluna `freeze_frame TEXT` migrada incremental,
  renderização no CLI (`ui.freeze_frame_panel`), no relatório (tabela
  antes da análise IA) e na UI web (painel paralelo a PIDs + badge ❄ no
  Dashboard / Histórico / linha do tempo da aba Evolução).
- **Captura contínua live data 60s** na aba **Scan**: novo botão 📊
  **Gravar 60s (live PIDs)** usa endpoint SSE `GET /api/scan/live?duration=`,
  lê PIDs a cada 1s via thread de fundo e renderiza 4 séries SVG polyline
  independentes (RPM + Coolant lado esquerdo, MAF + FT curto B1 lado
  direito), com contador e botão de parada.
- Triagem guiada estruturada (causas prováveis, testes sugeridos e o que não
  fazer) gerada a partir de DTCs + PIDs e persistida no histórico.
- Relatório HTML por sessão (`/report/{id}`) com botão de download
  (`/report/{id}/download`) e comparação automática com a sessão anterior do
  mesmo VIN.
- Comando `autodiag report <id> [--open]` para gerar e abrir o relatório em
  HTML sem depender do servidor web.
- Endpoint `GET /api/session/{id}`, `GET /api/vehicles`,
  `GET /api/vehicle/{vin}/history`, `GET /api/vehicle/{vin}/trends` (estatísticas
  e alertas por parâmetro), `GET /api/vehicle/{vin}/export.csv` e
  `GET /api/vehicle/{vin}/export.json` para consumo externo e oficina.
- Módulo [core/trend.py](src/autodiag/core/trend.py) com estatísticas por
  parâmetro (média, desvio-padrão, regressão linear simples via slope,
  z-score ≥ 2σ para outliers), detecção de recorrência de DTCs e alertas
  semânticos por threshold (high_bad / sym_bad / range_good).
- Nova aba **Evolução** na interface web: seleção de VIN, cards de tendência
  com sparkline SVG inline, seta de direção, variação percentual, σ e
  alertas de outlier/threshold; painel superior com alertas agregados;
  DTCs recorrentes (≥2 aparições); linha do tempo completa dos scans;
  botões de exportação CSV e JSON.

### Alterado

- A página de Histórico e o Dashboard passam a oferecer links diretos para
  abrir e baixar relatórios.
- A comparação do relatório agora inclui delta e variação percentual e filtra
  mudanças pequenas por thresholds.

### Corrigido

- `summary().last.dtc_codes` agora retorna lista (e não JSON bruto), alinhando
  o formato com `history()` e evitando inconsistência no Dashboard.

## [0.2.1] — 2026-07-27

### Corrigido

- A camada de display interpolava texto não confiável direto na marcação do
  `rich`, que trata `[algo]` como tag de estilo. Três efeitos, todos observados
  no 0.2.0:
  - a mensagem que orienta a instalar o backend opcional saía como
    `pip install 'autodiag'`, sem o `[openai]` — a instrução estava errada e
    deixava o usuário em loop;
  - trechos entre colchetes na análise da IA eram apagados em silêncio
    (`[ver P0101]` desaparecia do parecer);
  - uma tag de fechamento órfã na saída do modelo (`[/PCV]`) levantava
    `MarkupError`, então a chamada era paga e o parecer não aparecia.

  `ok`/`warn`/`err` agora passam por `rich.markup.escape`, e o painel de análise
  renderiza via `rich.text.Text`, que não parseia marcação.

### Adicionado

- 7 testes de regressão para o tratamento de marcação (89 → 96).

## [0.2.0] — 2026-07-26

### Adicionado

- Porta única para LLMs em `agents/provider.py`, com dois backends atrás da
  mesma interface: Anthropic nativo (streaming + thinking adaptativo) e
  qualquer endpoint OpenAI-compatible (OpenAI, OpenRouter, Groq, Together,
  vLLM, Ollama, LM Studio).
- Seleção de modelo por ambiente — `AUTODIAG_LLM_BACKEND`, `AUTODIAG_MODEL`,
  `AUTODIAG_BASE_URL`, `AUTODIAG_API_KEY` — e por `--model` na CLI.
- Extra opcional `autodiag[openai]` para o backend OpenAI-compatible.
- Tratamento de `stop_reason="refusal"`: a recusa por política de conteúdo
  retorna HTTP 200 com conteúdo vazio ou parcial e, sem esta checagem, o
  parecer sairia truncado em silêncio.
- Demo visual reproduzível da interface web, gerada com o adaptador simulado.
- Política de segurança, reporte privado de vulnerabilidades, CodeQL e
  atualizações automáticas de dependências.
- Cobertura ampliada de 67 para 89 testes.

### Alterado

- Modelo padrão da Anthropic: `claude-opus-4-8` → `claude-opus-5`.
- O modelo deixou de ser fixo no código: `DEFAULT_MODEL` em
  `agents/diagnostic.py` não existe mais; o parâmetro `model` de `analyze()`
  agora aceita `None` (usa o default do backend resolvido).
- Mensagens da CLI e da web deixaram de citar "Claude" e passam a nomear o
  modelo ativo.

## [0.1.0] — 2026-07-23

Primeira versão publicada.

### Adicionado

- Leitura de DTCs (modo 03) com decodificação SAE J2012 (códigos P/C/B/U) e
  base local com ~65 códigos descritos em português.
- Limpeza de DTCs (modo 04) com confirmação.
- PIDs ao vivo (modo 01): RPM, velocidade, temperaturas, borboleta, MAF,
  fuel trims, sonda O2 e nível de combustível.
- Identificação do veículo por VIN (decodificação local + API NHTSA vPIC).
- Heurística de urgência (`critico` / `atencao` / `informativo`).
- Análise opcional com IA (Claude Opus 4.8, streaming, thinking adaptativo).
- Histórico de diagnósticos em SQLite com listagem e resumo estatístico.
- Interface web (FastAPI) com scan em tempo real via Server-Sent Events.
- **Modo demo** (`--demo` / checkbox na web): adaptador simulado com cenário
  de mistura pobre + falha de ignição — roda sem hardware.
- Autodetecção de porta serial em Windows, Linux e macOS (pyserial).
- Suporte a adaptadores USB, Bluetooth serial e Wi-Fi (TCP).
- Suíte com 67 testes, lint (ruff) e type-check (mypy) no CI.

### Corrigido

- Decodificação de DTCs de chassi/carroceria/rede gerava códigos errados
  (ex.: `C0031` lido como `C4031`).
- Saída no console legado do Windows quebrava com `UnicodeEncodeError`
  (streams agora forçados a UTF-8).

[Não publicado]: https://github.com/lucianoon/autodiag/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/lucianoon/autodiag/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/lucianoon/autodiag/releases/tag/v0.1.0
