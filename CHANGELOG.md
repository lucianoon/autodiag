# Changelog

Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/);
versionamento segue [SemVer](https://semver.org/lang/pt-BR/).

## [Não publicado]

### Adicionado

- **Orçamento automático estimado por família DTC**: novo módulo
  [core/cost_estimates.py](src/autodiag/core/cost_estimates.py) com tabela
  de faixas em **centavos de Real** (`min_cents, max_cents`) por família
  de DTC (P00..P09, B0/B1, C0/C1, U0/U1) + multiplicadores por severidade
  (`critico` ×1.15/1.25, `atencao` ×1.0/1.05, `informativo` ×0.9/0.85).
  Funções `estimate_dtc_cost()`, `estimate_session_costs(lista)` e
  `format_brl(cents)` (formato BR `R$ 1.234,56`).
- **CLI: Painel de custos logo após o triage**: após cada scan, `autodiag scan`
  mostra `[cyan]Orçamento estimado[/]` rich-panel com: header "Faixa estimada" +
  tabela por DTC (código, descrição 120 chars, severidade colorida, faixa por item) +
  aviso legal regional Sudeste BR.
- **CLI: Persistência de orçamento no banco**: `Session.cost_min` / `cost_max`
  deixaram de ser `0` hardcoded no `cmd_scan` e agora recebem valores
  retornados por `estimate_session_costs()` antes do `History.save()`.
- **Relatório: Card 🛠️ Orçamento estimado**: inserido após Freeze+Readiness e
  antes de Análise IA**: mostra "Faixa total" em destaque azul, tabela 4 colunas
  (Código, Descrição, Badge Severidade, Faixa), aviso legal
  Sudeste-BR.
  **Retrocompatível: sessões antigas com cost_min/max salvos como 0 são recalculados
  on-the-fly a partir de `dtc_codes` antes do `s.get("dtc_codes")`. Caso
  limpo (sem DTCs) mostra o texto verde "Não há falhas identificadas — custo R$ 0,00`.
- **Exportação PDF do relatório (A4):
  - Dependência obrigatória `playwright>=1.45.0` no `pyproject.toml`.
  - Módulo novo [core/pdf.py](src/autodiag/core/pdf.py) com `render_url_to_pdf(url, output_path)`
    que: detecta ausência do `playwright`/Chromium levanta `RuntimeError`
    instruções, roda `sync_playwright()` headless, A4
    viewport 794×1123 (`networkidle`, margens 10/12mm, `print_background=True`
    para preservar CSS GitHub-Dark, remove antes de o PDF.
  - Endpoint novo **`GET /report/{sid}/pdf`**: faz o Chromium abrir o próprio
    `/report/{sid}` real (com `request.url_for("report")` com autenticação real do
    request corrente, gera PDF em `tempfile` temporário, retorna `StreamingResponse`
    `application/pdf` nome `autodiag-report-<vin6dig>-<ts>.pdf`;
    `playwright` indisponível cai em 503 JSON `{"error": "playwright_required", "detail": "..."}`.
  - UI 4️⃣ locais de botão 📄 PDF:
    (1) navbar do próprio relatório HTML (entre "Baixar HTML" e Imprimir);
    (2) card "Último scan" dashboard (Abrir relatório / 📄 PDF / Baixar HTML / ✎);
    (3) linha da tabela de histórico (✎/Relatório/📄/Baixar);
    (4) (opcional) link download direto `.pdf`.
- **Testes novos**: 19 casos a mais (+19 net):
  `tests/test_cost_estimates.py` 16 casos unitários `format_brl` (zero, cem reais,
  1.234, 10k); `estimate_dtc_cost` desconhecido → default; P0171 tem descrição;
  P0300 misfire é `critico`; B0001 airbag tem mín 30k; P0731 transmissão crítica
  mín 60k); `estimate_session_costs` (vazia; 1 code min>0; dup collapsa duplicados
  (P0171+P0171→2 itens; total soma matches individual; P0171+B0001+U0100 3 códigos
  faixas coerentes; códigos inválidos → ignorados).
  `test_report.py`: 2 novos `cost_block_appears_with_dtcs_and_estimated_values` 3 DTCs
  + "Sudeste do Brasil" aviso legal `cost_block_shows_zero_when_no_dtcs` texto
  verde "R$ 0,00 sem falhas".
  test_web.py`: TestApiReportPdf 2 casos: missing session sid inexistente → 404; runtime
  monkeypatch `render_url_to_pdf` lançar RuntimeError retorna 503 payload
  `playwright_required` mensagem coerente; se instalar rodar real valida magic
  `%PDF-` header 10KB mín size.
- **Segurança e validação no `PUT /api/branding`**: todos os 7 campos de
  branding agora têm sanitização server-side: `strip()`, limite de 160 chars
  por campo, e `logo_url` só aceita `http://`, `https://` ou
  `data:image/{png,jpeg,svg+xml};base64,` (até 2000 chars). Qualquer input
  fora dessas regras vira `""` em vez de ser salvo cru.
- **Soft-delete + purge de sessões (LGPD/LGPD)**: nova coluna `deleted_at`
  adicionada via migração incremental (bases antigas continuam funcionando).
  Novo `History.delete_session(sid, purge=False)` marca deleted_at com
  timestamp ISO; `purge=True` apaga fisicamente; `restore_session()` desfaz
  o soft-delete; `purge_deleted_older_than(days=30)` faz limpeza automática.
  Todos os reads (`list`, `get`, `list_by_vin`, `previous_for_vin`,
  `list_vehicles`, `summary`) agora ignoram deleted_at automaticamente.
- **Endpoint `DELETE /api/session/{sid}?purge=true|false`** expõe o
  soft-delete via API (retorna 404 quando sid não existe).
- **CORS liberado local-first**: FastAPI agora roda com `CORSMiddleware`
  `allow_origins=["*"]` e `max_age=3600`, eliminando erros intermitentes de
  navegador em acessos por IP da LAN ou com extensões injetando código.
- **QR code no footer do relatório**: `build_report()` agora aceita
  `download_url` extraído de `request.url_for()` nos endpoints `/report` e
  `/report/{sid}/download`. O render HTML injeta um card GitHub-Dark-style
  no final do documento com `<img src="data:image/png;base64,...">` gerado
  via `qrcode[pil]` (tamanho 96×96 px). Fallback: se o IP real não tiver
  disponível, usa socket.getaddrinfo + 8.8.8.8 connect pra descobrir IP LAN
  e cai pra localhost.
- **Captura live 60s: buffer completo + CSV download**:
  - Backend: endpoint `/api/scan/live` agora acumula `samples[]` em memória
    no loop daemon e, ao final, envia evento `done` com
    `{duration, samples:[{t,pids},...]}`, em vez de só `type:done`.
  - Frontend: botão 💾 "Baixar CSV" no card-header da captura começa
    disabled e fica habilitado no evento `done`. CSV tem 12 colunas (t + 11
    PIDs) codificado UTF-8 BOM + CRLF, nome `autodiag-live-YYYYMMDD-HHMMSS.csv`.
  - SVG é **rerenderizado** no evento `done` usando os samples[] oficiais,
    garantindo integridade completa do gráfico mesmo se algum tick se perdeu
    no render progressivo do EventSource.
- **pyproject.toml**: novas dependências obrigatórias `qrcode[pil]>=8.0` e
  `playwright>=1.45.0`.
- **Testes de endpoints web (P0.4)**: arquivo `tests/test_web.py` com
  20 cases: 8 em `PATCH /api/session/{sid}`, 4 em `DELETE /api/session/{sid}`,
  6 em `PUT/GET /api/branding`, 2 em `/api/scan/live`, 2 em
  `GET /report/{sid}/pdf` (404 + 503 playwright_required).

### Alterado

- Frontend startLiveCapture trocou query param `wifi=` por `wifi_host=`
  (match do nome real do parâmetro em `/api/scan/live`).
- Live SVG rendering extraído pra helper `_renderSeries(history, seconds)`
  compartilhado entre evento tick e evento done.
- CLI cmd_scan: `Session(cost_min, cost_max)` agora vem de
  `estimate_session_costs()` em vez de `0, 0` hardcoded.

### Corrigido

- FastAPI TestClient: testes de live captura agora usam contexto gerenciado
  `with client.stream(...)` em vez de kwarg `stream=True` (removido em
  httpx 0.27+).
- Mypy strict em `tests/test_reader.py` (status.monitors `dict[str, bool] | None`
  não indexável): introduzidos helpers locais `spark_mon = status.monitors or {}`
  com asserts `bool(...)`.
- Ruff UP035: test fixtures que usam `yield from typing.Iterator` migrados
  para `collections.abc.Iterator`.
- Ruff B904: raise HTTPException 500 no endpoint PDF agora tem
  `raise ... from e` (preserva cadeia de exceptions).

## [0.4.0] — 2026-08-06

### Adicionado

- **Base de DTCs expandida de 65 para 566 códigos**: novo módulo
  [core/dtc_catalog.py](src/autodiag/core/dtc_catalog.py) gera as famílias
  padronizadas SAE J2012 (quintetos de circuito por sensor, sextetos de sonda
  lambda por banco/sensor, injetores e misfire por cilindro 1–12, solenoides
  de câmbio A–E, módulos de rede U0xxx) com descrição PT-BR, severidade,
  sistema e causas prováveis por tipo de falha. A base curada tem precedência
  via `dtc.full_database()`; a busca `GET /api/dtc` cobre o catálogo inteiro.
- **Prontidão dos monitores (readiness) completa**: o modo 01 PID 01 agora
  decodifica os bytes B/C/D (monitores contínuos e não-contínuos, tabelas de
  centelha e compressão), além dos PIDs 30 (ciclos de aquecimento desde a
  limpeza) e 31 (distância desde a limpeza).
- **Detecção de limpeza recente de códigos** (novo módulo
  [core/readiness.py](src/autodiag/core/readiness.py)): zero DTCs + monitores
  incompletos + pouca rodagem desde a limpeza geram veredicto estruturado
  (`suspeito`/`normal`/`inconclusivo`, com confiança, evidências e
  recomendação) — o quadro típico de scan apagado antes de vistoria de
  seminovo. Exibido na CLI, na web (card no Scan), persistido no histórico
  (coluna `readiness`, migração incremental) e incluído no relatório HTML.
- No modo demo, apagar os DTCs e escanear de novo reproduz o cenário de
  adulteração e dispara a detecção — o fluxo inteiro é testável sem hardware.
- **Infraestrutura de comunidade**: CONTRIBUTING.md, matriz de
  compatibilidade ([docs/compatibilidade.md](docs/compatibilidade.md)),
  formulários de issue (relato de compatibilidade, bug, feature), Discussions
  habilitadas e primeiras issues `good first issue`.
- **Interface web instalável (PWA)**: manifest e ícone servidos em
  `/static`, `theme-color` e favicon SVG — no celular, "Adicionar à tela
  inicial" abre o AutoDiag em janela própria apontando para o notebook ou
  Raspberry na mesma rede.
- **Primeiros testes da API web** (`tests/test_web.py`, TestClient com banco
  isolado): index, manifest, detalhe/busca de DTC cobrindo o catálogo novo,
  summary e PATCH 404.
- **Parecer de vistoria padronizado** no relatório (novo módulo
  [core/inspection.py](src/autodiag/core/inspection.py)): urgência, DTCs e a
  verificação de limpeza de códigos consolidados em um veredicto de quatro
  níveis — Aprovado / Aprovado com ressalvas / Reinspeção necessária /
  Reprovado — com razões e recomendação, em banner no topo do laudo. Inclui a
  ressalva de escopo (diagnóstico eletrônico OBD2, não substitui inspeção
  mecânica).

## [0.3.0] — 2026-08-06

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
- `History` ganhou `close()` e suporte a context manager; CLI, servidor web e
  testes fecham a conexão SQLite explicitamente.
- A CI passou a rodar também no Windows (`ubuntu-latest` + `windows-latest`),
  plataforma predominante do público-alvo da ferramenta.
- A comparação do relatório agora inclui delta e variação percentual e filtra
  mudanças pequenas por thresholds.

### Corrigido

- `summary().last.dtc_codes` agora retorna lista (e não JSON bruto), alinhando
  o formato com `history()` e evitando inconsistência no Dashboard.
- No Windows, a conexão SQLite aberta pela `History` mantinha o `history.db`
  travado indefinidamente (impedindo mover ou apagar o arquivo com o app
  aberto) e derrubava um teste na limpeza do diretório temporário.
- `PATCH /api/session/{sid}` com corpo vazio em sessão inexistente agora
  retorna 404 de verdade (antes devolvia o objeto `HTTPException` serializado
  com status 200).

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

[Não publicado]: https://github.com/lucianoon/autodiag/compare/v0.4.0...HEAD
[0.4.0]: https://github.com/lucianoon/autodiag/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/lucianoon/autodiag/compare/v0.2.1...v0.3.0
[0.2.1]: https://github.com/lucianoon/autodiag/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/lucianoon/autodiag/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/lucianoon/autodiag/releases/tag/v0.1.0
