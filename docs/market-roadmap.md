# AutoDiag: Roadmap de Diferenciacao do Scan

## Resumo executivo

Hoje o AutoDiag ja e um produto tecnico convincente para OBD2 generico:
faz scan real, tem modo demo, historico local, web UI, heuristica de urgencia
e camada opcional de IA. Isso o coloca acima de um projeto de portfolio
"script + LLM".

Mas ele ainda nao se destaca no mercado se for apresentado como "mais um
scanner OBD2". Nesse espaco, a concorrencia ja tem:

- apps baratos e maduros para usuario final
- scanners profissionais com cobertura por fabricante
- plataformas de oficina com fluxo de atendimento e relatorio

A oportunidade do AutoDiag nao esta em competir como scanner generico, e sim
em virar um **scanner de diagnostico guiado e explicavel**, com foco em
triagem, decisao e proxima acao recomendada.

## Leitura honesta do produto hoje

### Onde o scan ja esta forte

- leitura de DTCs e PIDs de motor/emissoes
- identificacao do veiculo por VIN
- classificacao inicial de urgencia
- historico local por sessao
- experiencia multimodal: CLI + web + demo
- camada de IA desacoplada do provider

### Onde o scan ainda esta fraco

- cobertura profunda por modulo (ABS, airbag, TCM, BCM, EPS)
- freeze frame e readiness monitors mais completos
- captura continua de live data com comparacao temporal
- diagnostico guiado por sintoma e contexto
- relatorio profissional para cliente/oficina
- inteligencia por marca/modelo/motor/cenario

## Tese de diferenciacao

O AutoDiag deve ser posicionado como:

**"Diagnostico automotivo guiado, explicavel e local-first para triagem
tecnica rapida."**

Nao como:

- "scanner universal completo"
- "substituto de Launch/Autel/Bosch"
- "mais um leitor de codigo com IA"

## ICP recomendado

O ICP mais promissor para a primeira fase e:

**Oficina pequena / tecnico independente / consultor automotivo leve**

### Por que esse ICP faz sentido

- sente dor real em triagem rapida
- nao precisa, no dia 1, de cobertura OEM tao profunda quanto uma oficina
  premium multimarca
- valoriza explicacao e priorizacao, nao apenas leitura de codigo
- pode usar web/desktop local sem friccao
- aceita bem historico, relatorio e passo a passo de verificacao

### ICPs secundarios

1. comprador de carros usados / vistoria rapida
2. dono de carro entusiasta
3. consultoria remota de diagnostico

## O que vai diferenciar de verdade

### 1. Diagnostico explicavel

Nao basta mostrar:

- DTC
- PID
- urgencia

Precisa mostrar:

- qual conjunto de sinais sustenta a hipotese
- o que e causa provavel vs sintoma
- qual teste deve vir antes
- o que o usuario nao deve trocar sem validar

### 2. Fluxo de triagem guiada

O diferencial nao e "mais IA". E:

- detectar padroes
- transformar leitura em ordem de verificacao
- reduzir troca de peca por tentativa

Exemplo:

`P0171 + MAF baixo + fuel trim alto + O2 baixo`

Saida diferenciada:

- hipotese principal: entrada falsa de ar / admissao
- evidencias observadas
- testes sugeridos em ordem
- risco de continuar rodando
- pecas que nao devem ser trocadas antes do teste X

### 3. Historico com comparacao

O scan ganha muito valor quando responde:

- piorou ou melhorou desde o ultimo atendimento?
- esse DTC e recorrente?
- os trims estao convergindo?
- o reparo anterior alterou o comportamento?

### 4. Relatorio comercial

Para virar produto de mercado, o scan precisa terminar em um artefato
compartilhavel:

- resumo executivo do problema
- severidade
- proximos testes
- recomendacao de uso ou parada
- observacoes tecnicas

## Roadmap recomendado

## Fase 1: Fortalecer a decisao tecnica

Objetivo: sair de "scanner com leitura" para "scanner com triagem util".

Entregas:

- expandir heuristicas por padrao de falha
- adicionar explicacao estruturada por evidencias
- incluir freeze frame quando disponivel
- enriquecer readiness/monitor status
- classificar "pode rodar / rodar com cautela / parar"

Resultado esperado:

- valor perceptivel mesmo sem cobertura OEM

## Fase 2: Melhorar operacao real

Objetivo: virar ferramenta de uso recorrente.

Entregas:

- sessao de live data continua com timeline/graficos
- comparacao entre scans do mesmo veiculo
- relatorio exportavel
- tags e notas por atendimento
- biblioteca de cenarios de falha recorrente

Resultado esperado:

- uso repetido por oficina pequena ou consultor

## Fase 3: Verticalizar inteligencia

Objetivo: ganhar vantagem dificil de copiar.

Entregas:

- perfis por montadora / motor / ano
- regras e thresholds por familia de veiculo
- playbooks de diagnostico por cenario
- cobertura progressiva de modulos alem de motor/emissoes

Resultado esperado:

- diferenciacao estrutural, nao apenas UX

## Fase 4: Produto vendavel

Objetivo: transformar tecnologia em oferta comercial clara.

Entregas:

- relatorio profissional com branding
- historico por cliente/veiculo
- modos de uso por persona
- onboarding orientado a caso de uso
- metricas de tempo de triagem e recorrencia de falhas

Resultado esperado:

- narrativa de valor clara para venda

## Prioridades de implementacao

Se eu tivesse que escolher apenas 5 proximos blocos, eu faria nesta ordem:

1. explicacao estruturada do diagnostico
2. freeze frame + monitor/readiness melhorados
3. comparacao entre sessoes do mesmo veiculo
4. relatorio exportavel
5. biblioteca de padroes de falha guiados

## Mensagem de mercado recomendada

Evitar:

- "scanner OBD2 com IA"
- "diagnostico automotivo universal completo"

Usar:

- "triagem automotiva guiada e explicavel"
- "scanner local-first para diagnostico orientado a decisao"
- "reduz troca por tentativa e acelera a primeira leitura tecnica"

## O que medir

Para saber se o scan esta ficando mais competitivo, medir:

- tempo ate primeira hipotese util
- percentual de scans com recomendacao acionavel
- recorrencia de DTC por veiculo
- taxa de uso do historico
- taxa de uso do relatorio exportado
- tempo entre scan e decisao de proxima acao

## Proximo passo recomendado

O proximo movimento mais valioso nao e tentar "ler mais modulos" de imediato.
E transformar o scan atual em **motor de triagem guiada**.

Recomendacao pratica:

1. estruturar o diagnostico em blocos formais:
   - sinais observados
   - causa provavel
   - testes sugeridos
   - risco operacional
   - o que nao fazer
2. persistir isso no historico
3. exibir isso claramente na web e no relatorio

Quando isso estiver forte, vale aprofundar OEM e modulos adicionais.
