# Changelog

Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/);
versionamento segue [SemVer](https://semver.org/lang/pt-BR/).

## [Não publicado]

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
