# Changelog

Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/);
versionamento segue [SemVer](https://semver.org/lang/pt-BR/).

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

[0.1.0]: https://github.com/lucianoon/autodiag/releases/tag/v0.1.0
