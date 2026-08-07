# Changelog

Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/);
versionamento segue [SemVer](https://semver.org/lang/pt-BR/).

## [Não publicado]

### Adicionado

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
- **pyproject.toml**: nova dependência obrigatória `qrcode[pil]>=8.0`.
- **Testes de endpoints web (P0.4)**: novo arquivo `tests/test_web.py` com
  18 cases: 8 em `PATCH /api/session/{sid}` (tags invalidas/limites/trim,
  notes invalido, 404), 4 em `DELETE /api/session/{sid}` (soft vs purge vs
  restore vs 404), 6 em `PUT/GET /api/branding` (tamanho 160, XSS
  `logo_url`, data:image, campos desconhecidos, roundtrip), 2 em
  `/api/scan/live` (clamp duration negativo -> 1 tick, callable 600 clamp).

### Alterado

- Frontend startLiveCapture trocou query param `wifi=` por `wifi_host=`
  (match do nome real do parâmetro em `/api/scan/live`).
- Live SVG rendering extraído pra helper `_renderSeries(history, seconds)`
  compartilhado entre evento tick e evento done.

### Corrigido

- FastAPI TestClient: testes de live captura agora usam contexto gerenciado
  `with client.stream(...)` em vez de kwarg `stream=True` (removido em
  httpx 0.27+).
- Mypy strict em `tests/test_reader.py` (status.monitors `dict[str, bool] | None`
  não indexável): introduzidos helpers locais `spark_mon = status.monitors or {}`
  com asserts `bool(...)`.
- Ruff UP035: test fixtures que usam `yield from typing.Iterator` migrados
  para `collections.abc.Iterator`.

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
