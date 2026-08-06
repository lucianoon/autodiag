# Matriz de compatibilidade

Relatos reais de veículos testados com o AutoDiag, mantidos pela comunidade.
Cada linha vem de um [relato de compatibilidade](../../../issues/new?template=compatibilidade.yml)
— contribua com o seu, funcionando ou não.

**Legenda:** ✅ funciona · ⚠️ parcial (detalhe na issue) · ❌ não funcionou

## Veículos testados

| Veículo | Ano | Motor | Adaptador | Conexão | DTCs | PIDs | VIN | Readiness | Relato |
|---|---|---|---|---|---|---|---|---|---|
| _Aguardando o primeiro relato da comunidade_ | | | | | | | | | |

> O veículo simulado do modo demo (`autodiag scan --demo`) reproduz um
> VW Gol 2019 com P0171/P0300 e cobre 100% dos fluxos sem hardware — mas
> nada substitui relato de carro de verdade.

## Adaptadores testados

| Adaptador | Chipset | Conexão | Observações | Relato |
|---|---|---|---|---|
| _Aguardando o primeiro relato_ | | | | |

## Como contribuir com um relato

1. Rode `autodiag scan` (ou `autodiag serve` e escaneie pela web) no veículo.
2. Anote o que funcionou e o que não funcionou (DTCs, PIDs, VIN, readiness).
3. Abra o [formulário de relato](../../../issues/new?template=compatibilidade.yml).
4. A linha entra na matriz no próximo PR de atualização (ou envie você mesmo
   o PR editando este arquivo — conta como contribuição!).
