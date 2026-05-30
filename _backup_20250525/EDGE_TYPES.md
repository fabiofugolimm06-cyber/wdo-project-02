# EDGE_TYPES.md
# WDO-EVOLVED-QUANT — Taxonomia de Tipos de Edge
# Ativo: WDO (Mini Dólar B3) | Gráfico: Renko 8R | Janela: 10:00–12:30
# Versão: 1.0 | Status: AGUARDANDO VALIDAÇÃO DeepSeek R1

---

## DEFINIÇÃO FORMAL

Um **edge** é uma assimetria estatisticamente verificável entre a distribuição
de retornos condicionada a um conjunto de estados observáveis e a distribuição
incondicional do mesmo ativo no mesmo período.

Edge não é padrão visual. Edge não é "setup". Edge é vantagem probabilística
mensurável com degradação previsível.

---

## HIERARQUIA DE CLASSIFICAÇÃO

```
EDGE_CLASS (nível 1)
  └── EDGE_TYPE (nível 2)
        └── EDGE_INSTANCE (nível 3 — criado no Edge Registry)
```

---

## CLASSES E TIPOS

---

### CLASSE 1 — VOLATILITY_DYNAMICS

Edges baseados em comportamento mensurável da volatilidade intraday.

---

#### ET-VOL-01 | VOLATILITY_EXPANSION

**Definição:** Estado de compressão de range precede expansão direcional
com probabilidade acima da base.

**Mecanismo:** Acumulação de posições em range estreito cria desequilíbrio
latente. Quando o preço rompe o nível de compressão, ordens represadas
alimentam momentum unidirecional.

**Condição necessária:** ATR das últimas N velas abaixo da média histórica
do período — compressão real, não apenas velas pequenas isoladas.

**Condição suficiente:** Rompimento físico confirmado com volume acima
da média de 20 velas.

**Fonte primária:** Crabel (range contraction → expansion), Northington
(volatility regime classification), Clenow (momentum trigger post-compression)

**Restrições de execução WDO:**
- Rompimento mínimo: 0,5 ponto (Confirmação Vela 2)
- ATR não pode estar acima de 1,5x médio (Filtro Northington ativo)
- Válido somente dentro da Janela de Ouro 10:00–12:30

**Failure modes associados:** FM-001, FM-003, FM-006

---

#### ET-VOL-02 | VOLATILITY_CONTRACTION

**Definição:** Estado de expansão excessiva de volatilidade é seguido por
contração e retorno ao regime normal com probabilidade acima da base.

**Mecanismo:** Choques de volatilidade extrema esgotam participantes
direcionais. O mercado entra em modo de digestão, reduzindo range e ATR
progressivamente.

**Condição necessária:** ATR atual > 1,5x ATR médio (regime de choque).

**Condição suficiente:** Ausência de catalisador externo sustentado
(macro, Fed, dados).

**Fonte primária:** Northington (volatility spike classification),
Kleppmann (regime state transitions)

**Restrições de execução WDO:**
- Este edge é primariamente um **sinal de bloqueio**, não de entrada.
- Quando ativo, o sistema entra em modo Sentinela.
- Não gera ordens — gera inatividade protegida.

**Failure modes associados:** FM-007

---

#### ET-VOL-03 | PARTICIPATION_SURGE

**Definição:** Aumento súbito de volume (agressão) em direção única precede
movimento direcional sustentado com probabilidade acima da base.

**Mecanismo:** Fluxo institucional detectável via intensidade de agressão.
Grandes participantes não conseguem ocultar completamente o footprint
de entrada.

**Condição necessária:** Volume da vela de sinal > média de 20 velas.

**Condição suficiente:** Times & Trades confirma direção dominante
(agressores na mesma direção do rompimento).

**Fonte primária:** Northington (participation analysis),
Harris v2 (order flow imbalance), Dalton (auction participation)

**Restrições de execução WDO:**
- Sinal descartado como FALTA_DE_FLUXO se volume não confirmar.
- Latência máxima: 1 vela (100–500ms contexto retail).

**Failure modes associados:** FM-004, FM-005

---

### CLASSE 2 — MOMENTUM_STRUCTURE

Edges baseados em persistência direcional do preço.

---

#### ET-MOM-01 | MOMENTUM_CONTINUATION

**Definição:** Movimento direcional estabelecido tende a continuar por
período mensurável antes da reversão, especialmente quando confirmado
por estrutura de velas consecutivas.

**Mecanismo:** Posicionamento direcional de participantes cria pressão
contínua enquanto o desequilíbrio não é absorvido. No Renko 8R, cada
vela nova na mesma direção representa 8 pontos de movimento real —
confirmação de força estrutural.

**Condição necessária:** Sequência de pelo menos 2 velas na mesma direção
no Renko 8R, com Vela 2 rompendo fisicamente a máxima/mínima da Vela 1
em ≥ 0,5 ponto.

**Condição suficiente:** Rompimento físico confirmado + volume acima da
média + dentro da Janela de Ouro.

**Fonte primária:** Clenow (trend following principles), Harris v2
(momentum persistence), Northington (Vela 2 confirmation)

**Restrições de execução WDO:**
- Confirmação Vela 2 é obrigatória e inegociável.
- Compra: close_vela2 > high_vela1 + 0,5
- Venda: close_vela2 < low_vela1 − 0,5

**Failure modes associados:** FM-002, FM-005, FM-008

---

#### ET-MOM-02 | BREAKOUT_CONFIRMATION

**Definição:** Rompimento de nível estrutural relevante com confirmação
de volume e fechamento além do nível precede movimento direcional com
probabilidade acima da base.

**Mecanismo:** Concentração de ordens stop e limite em torno de níveis
estruturais cria catalisador de liquidez quando rompidos. O rompimento
confirmado ativa ordens represadas dos dois lados.

**Condição necessária:** Preço fecha além de nível estrutural identificável
por pelo menos 3 toques anteriores.

**Condição suficiente:** Fechamento além do nível + volume de confirmação
+ manutenção por pelo menos 1 vela de consolidação acima/abaixo.

**Fonte primária:** Crabel (breakout methodology), Dalton (market profile
breakout), Carver (systematic breakout entry)

**Restrições de execução WDO:**
- Rompimento falso é o principal failure mode — ver FM-002.
- Exige ATR dentro do regime normal (Filtro Northington).

**Failure modes associados:** FM-002, FM-001, FM-004

---

### CLASSE 3 — AUCTION_DYNAMICS

Edges baseados na estrutura de leilão do mercado intraday.

---

#### ET-AUC-01 | AUCTION_IMBALANCE

**Definição:** Desequilíbrio entre compradores e vendedores na estrutura
de leilão intraday cria pressão direcional com probabilidade acima da base.

**Mecanismo:** O mercado funciona como leilão bilateral. Quando um lado
domina consistentemente o processo de leilão (confirmado por perfil de
volume e estrutura de TPO), o preço é forçado a descobrir novo valor.

**Condição necessária:** Estrutura de POC em posição assimétrica,
com desenvolvimento de valor favorecendo uma direção.

**Condição suficiente:** Agressão confirmada na direção do desequilíbrio
durante a Janela de Ouro.

**Fonte primária:** Dalton (market profile / auction theory),
Harris v2 (order flow and auction structure)

**Restrições de execução WDO:**
- Requer contexto de Trend Day ou Opening Imbalance (ver MARKET_REGIMES.md).
- Em Rotation Day, este edge perde validade estrutural.

**Failure modes associados:** FM-007, FM-003

---

#### ET-AUC-02 | OPENING_IMBALANCE

**Definição:** Desequilíbrio de leilão no período de abertura (10:00–10:30)
estabelece direção preferencial para o restante da Janela de Ouro.

**Mecanismo:** Resolução de posições overnight + novo fluxo para sessão NY
= janela de desequilíbrio com direção identificável via primeiras velas.

**Condição necessária:** Velas iniciais da Janela de Ouro estabelecem
direção clara com volume acima da média.

**Condição suficiente:** Manutenção da direção após os primeiros 15 minutos
(10:15) sem reversão significativa.

**Fonte primária:** Dalton (opening imbalance theory),
Northington (session transition analysis)

**Restrições de execução WDO:**
- Janela de identificação: 10:00–10:45.
- Após 10:45, confirmar se o imbalance inicial ainda está ativo.

**Failure modes associados:** FM-007, FM-006

---

### CLASSE 4 — TEMPORAL_STRUCTURE

Edges baseados em padrões temporais mensuráveis intraday.

---

#### ET-TMP-01 | TIME_OF_DAY

**Definição:** Determinados períodos intraday apresentam distribuição de
retornos estatisticamente diferente da distribuição média do dia inteiro.

**Mecanismo:** Estrutura institucional de participação varia ao longo
do dia. Abertura NY, fechamento de posições antes de dados macro,
sobreposição de sessões — criam padrões temporais repetíveis.

**Condição necessária:** Análise estatística confirmando assimetria de
retornos no período identificado vs. distribuição incondicional.

**Condição suficiente:** Assimetria persistente em múltiplos períodos
de walk-forward (critério Pardo: degradação OOS < 20%).

**Fonte primária:** Northington (Golden Window definition),
Pardo (temporal edge validation), Donnelly (intraday seasonality)

**Restrições de execução WDO:**
- A Janela de Ouro 10:00–12:30 é a materialização deste edge.
- Fora desta janela: modo Sentinela obrigatório.

**Failure modes associados:** FM-007, FM-008

---

#### ET-TMP-02 | SESSION_TRANSITION

**Definição:** A transição entre sessões cria padrões de volatilidade
e direção com probabilidade acima da base.

**Mecanismo:** Resolução de posições da sessão anterior + novo fluxo
da sessão entrante = janela de desequilíbrio temporário com direção
identificável via primeiras velas.

**Condição necessária:** Identificação da transição de sessão ativa.

**Condição suficiente:** Confirmação de direção via Vela 2 nos primeiros
15 minutos da transição.

**Fonte primária:** Dalton, Northington, Donnelly

**Restrições de execução WDO:**
- Monitorar sobreposição 13:00–13:30 (abertura NY) como potencial
  disruptor do edge primário da Janela de Ouro.

**Failure modes associados:** FM-006, FM-007

---

### CLASSE 5 — MEAN_REVERSION

Edges baseados em retorno à média após desvio estatisticamente extremo.

---

#### ET-REV-01 | MEAN_REVERSION

**Definição:** Desvio extremo do preço em relação a níveis de valor justo
identificados é seguido por retorno com probabilidade acima da base.

**Mecanismo:** Preço distante da área de valor justo atrai participantes
dispostos a negociar na direção contrária ao desvio, criando pressão
de reversão.

**Condição necessária:** Preço em desvio > 2x ATR médio do ponto de valor.

**Condição suficiente:** Sinais de exaustão (velas de reversão, redução
de agressão na direção do desvio).

**Fonte primária:** Carver (mean reversion systems),
Tharp (expectancy in mean reversion setups), Dalton (return to value)

**Restrições de execução WDO:**
- ⚠️ ATENÇÃO: Este edge é estruturalmente oposto ao ET-MOM-01.
  Os dois NÃO podem coexistir no mesmo sinal sem regime discriminador.
- Exige definição explícita de regime em MARKET_REGIMES.md antes de uso.

**Failure modes associados:** FM-007, FM-003, FM-001

---

### CLASSE 6 — LIQUIDITY_STRUCTURE

Edges baseados em comportamento de liquidez e order book.

---

#### ET-LIQ-01 | LIQUIDITY_IMBALANCE

**Definição:** Assimetria mensurável entre liquidez disponível nos dois
lados do book precede movimento direcional com probabilidade acima da base.

**Mecanismo:** Quando um lado do book é significativamente mais fino que
o outro, ordens de mercado de tamanho moderado criam movimento
desproporcional na direção do lado fino.

**Condição necessária:** Desequilíbrio de book identificável via
profundidade L2 ou proxy via Times & Trades.

**Condição suficiente:** Desequilíbrio sustentado por pelo menos 2
velas + agressão confirmada.

**Fonte primária:** Harris v2 (liquidity and market microstructure),
Donnelly (order flow and liquidity)

**Restrições de execução WDO:**
- Infraestrutura retail limita acesso a dados L2 de qualidade.
- Proxy via T&T é aceitável mas com confiança reduzida.
- Latência 100–500ms é crítica para este edge específico.

**Failure modes associados:** FM-004, FM-005, FM-009

---

## TABELA DE REFERÊNCIA RÁPIDA

| ID        | Nome                   | Classe              | Failure Modes     | Fonte Primária              |
|-----------|------------------------|---------------------|-------------------|-----------------------------|
| ET-VOL-01 | VOLATILITY_EXPANSION   | VOLATILITY_DYNAMICS | FM-001,003,006    | Crabel, Northington, Clenow |
| ET-VOL-02 | VOLATILITY_CONTRACTION | VOLATILITY_DYNAMICS | FM-007            | Northington, Kleppmann      |
| ET-VOL-03 | PARTICIPATION_SURGE    | VOLATILITY_DYNAMICS | FM-004,005        | Northington, Harris v2      |
| ET-MOM-01 | MOMENTUM_CONTINUATION  | MOMENTUM_STRUCTURE  | FM-002,005,008    | Clenow, Harris v2           |
| ET-MOM-02 | BREAKOUT_CONFIRMATION  | MOMENTUM_STRUCTURE  | FM-002,001,004    | Crabel, Dalton, Carver      |
| ET-AUC-01 | AUCTION_IMBALANCE      | AUCTION_DYNAMICS    | FM-007,003        | Dalton, Harris v2           |
| ET-AUC-02 | OPENING_IMBALANCE      | AUCTION_DYNAMICS    | FM-007,006        | Dalton, Northington         |
| ET-TMP-01 | TIME_OF_DAY            | TEMPORAL_STRUCTURE  | FM-007,008        | Northington, Pardo          |
| ET-TMP-02 | SESSION_TRANSITION     | TEMPORAL_STRUCTURE  | FM-006,007        | Dalton, Donnelly            |
| ET-REV-01 | MEAN_REVERSION         | MEAN_REVERSION      | FM-007,003,001    | Carver, Tharp, Dalton       |
| ET-LIQ-01 | LIQUIDITY_IMBALANCE    | LIQUIDITY_STRUCTURE | FM-004,005,009    | Harris v2, Donnelly         |

---

## REGRAS DE USO

1. Nenhum edge no Edge Registry pode existir sem estar vinculado a
   exatamente um ET-XXX desta tabela.

2. Se um edge candidato não se encaixa em nenhum tipo existente,
   um novo ET deve ser criado ANTES de registrar o edge.

3. Edges do mesmo ET são candidatos a semantic duplication —
   verificação obrigatória antes de criar novo registro.

4. ET-REV-01 e ET-MOM-01 são mutuamente exclusivos no mesmo sinal.
   O regime de mercado (MARKET_REGIMES.md) é o discriminador.

---

## NOTAS DE AUDITORIA

- Gerado por: Claude Sonnet (assistente)
- Validação pendente: DeepSeek R1 com DeepThink ativado
- Clusters fonte: Harris v2, Pardo, Crabel, Northington, Vince,
  Tharp, Carver, Clenow, Kleppmann, Dalton, Donnelly
- Restrição ativa: nenhum edge individual foi extraído aqui —
  apenas categorias estruturais (pré-canonicalização)
