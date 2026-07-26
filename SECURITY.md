# Política de segurança

## Versões suportadas

A versão mais recente publicada no PyPI e o branch `main` recebem correções de
segurança.

## Reportar uma vulnerabilidade

Não abra uma issue pública. Use **Security → Report a vulnerability** neste
repositório para enviar o relato de forma privada.

Inclua o commit ou versão afetada, impacto, passos mínimos para reprodução e,
se possível, uma mitigação. O objetivo é confirmar o recebimento em até 3 dias
úteis e publicar uma avaliação inicial em até 7 dias úteis.

## Escopo sensível

São especialmente relevantes relatos sobre:

- comandos OBD2 enviados sem confirmação;
- exposição de VIN, histórico local ou chaves de API;
- comunicação com adaptadores ELM327 não confiáveis;
- injeção de conteúdo nas explicações geradas por LLM;
- endpoints web acessíveis além da máquina local.

Não inclua VINs reais, dados pessoais, chaves ou segredos de produção.
