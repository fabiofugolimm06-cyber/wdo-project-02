# CANONICALIZATION_SPEC.md
# WDO-EVOLVED-QUANT | /03_EDGE_TAXONOMY
# Versão: 1.0 | Status: AGUARDANDO VALIDAÇÃO DeepSeek R1

---

## DEFINIÇÃO OPERACIONAL DE CANONICALIZATION

Canonicalization é o processo de transformar **conhecimento narrativo de clusters auditados**
em **unidades formais computáveis** — os Canonical Edges.

Entrada: texto de cluster auditado (RAW CLEAN) em /03_CANONICAL_KNOWLEDGE
Saída: Canonical Edge estruturado em /04_CANONICAL_KNOWLEDGE

Um Canonical Edge é a menor unidade de edge que pode ser:
- implementada em código
- testada isoladamente
- validada estatisticamente
- atribuída a uma fonte primária

---

## POR QUE CANONICALIZATION É NECESSÁRIA

Sem este processo:

**Problema 1 — Semantic Duplication:**
```
Crabel:      "narrow range contraction precedes directional expansion"
Northington: "volatility release after compression"
```
Sem canonicalization: dois edges no registry com mecanismo idêntico.
Com canonicalization: um único canonical (VOL_EXP_001) com duas fontes.

**Problema 2 — Implementação Ambígua:**
```
Harris v2: "two-bar momentum pattern"
```
O que exatamente é "two-bar"? Qual threshold? Qual volume?
A canonicalization força a resolução de toda ambiguidade antes do código.

**Problema 3 — Atribuição Incorreta:**
Sem canonicalization, não é possível saber qual autor contribuiu com qual componente do sistema.
Isso impossibilita auditoria e debugging quando um edge degrada.

---

## ESTRUTURA DO CANONICAL EDGE

Todo Canonical Edge deve ter TODOS os campos abaixo preenchidos.
Campo vazio = canonicalization incompleta = não vai para o Edge Registry.

```yaml
CANONICAL_EDGE:

  # IDENTIFICAÇÃO
  EDGE_ID:           string    # formato: TIPO_CLASSE_NNN (ex: VOL_EXP_001)
  EDGE_TYPE:         string    # referência a EDGE_TYPES.md
  VERSION:           string    # 1.0 inicial
  STATUS:            string    # DRAFT | VALIDATED | DEPRECATED

  # ORIGEM
  PRIMARY_SOURCE:    string    # autor principal (único)
  SECONDARY_SOURCES: list      # autores que corroboram (pode ser vazio)
  CLUSTER_IDS:       list      # IDs dos clusters de origem

  # MECANISMO
  MECHANISM:
    DESCRIPTION:     string    # descrição em 1-2 frases, sem jargão de trading
    MARKET_LOGIC:    string    # por que este edge existe (causa raiz)
    REGIME_VALIDITY: list      # regimes de MARKET_REGIMES.md onde é válido

  # COMPONENTES ONTOLÓGICOS (referência a SIGNAL_ONTOLOGY.md)
  SETUP:
    CONDITIONS:      list      # lista de condições de contexto
    Constraints:     list      # referências a EXECUTION_CONSTRAINTS.md

  TRIGGER:
    ID:              string    # referência a SIGNAL_ONTOLOGY.md TRG-XX
    OBSERVABLE:      string    # o que exatamente é observado
    MEASUREMENT:     string    # como medir (fórmula ou condição booleana)

  CONFIRMATION:
    IDS:             list      # referências a SIGNAL_ONTOLOGY.md CNF-XX
    LOGIC:           string    # AND / OR entre confirmações
    IMPLEMENTATION:  code      # pseudocódigo Python

  FILTERS:
    HARD:            list      # referências a FLT-BLK-XX
    SOFT:            list      # referências a FLT-QUA-XX

  INVALIDATION:
    CONDITIONS:      list      # referências a INV-XX

  # PARÂMETROS
  PARAMETERS:
    FIXED:           dict      # parâmetros fixos (não otimizáveis)
    CALIBRATABLE:    dict      # parâmetros que podem ser ajustados (com limites)

  # FAILURE MODES
  FAILURE_MODES:
    PRIMARY:         list      # failure modes mais prováveis (ref FAILURE_MODES.md)
    DETECTION:       list      # como detectar cada um

  # EXECUÇÃO
  EXECUTION:
    DIRECTION:       string    # LONG | SHORT | BOTH
    ENTRY_TYPE:      string    # MARKET | LIMIT
    STOP_TYPE:       string    # DYNAMIC_ATR (sempre)
    STOP_FORMULA:    string    # fórmula exata do stop
    TARGET_TYPE:     string    # ATR_MULTIPLE | FIXED_RATIO | TRAILING
    HOLDING_PERIOD:  string    # estimativa de duração do trade

  # VALIDAÇÃO
  VALIDATION:
    MINIMUM_TRADES:  int       # mínimo de trades para validação estatística
    WALKFORWARD:     bool      # walk-forward obrigatório (sempre true)
    OOS_DEGRADATION: float     # degradação máxima IS→OOS aceita (Pardo: 0.20)
    METRICS:         list      # métricas de validação

  # NOTAS
  SEMANTIC_DUPLICATES_CHECKED: bool   # duplicatas verificadas antes de registrar
  NOTES:             string           # observações do canonicalizador
```

---

## EXEMPLO DE CANONICAL EDGE COMPLETO

```yaml
CANONICAL_EDGE:

  EDGE_ID:           VOL_EXP_001
  EDGE_TYPE:         VOL_EXP (VOLATILITY_EXPANSION)
  VERSION:           1.0
  STATUS:            DRAFT

  PRIMARY_SOURCE:    Crabel (Toby Crabel — Day Trading with Short Term Price Patterns)
  SECONDARY_SOURCES:
    - Northington (Kirk Northington — Volatility-Based Technical Analysis)
    - Clenow (Andreas Clenow — Stocks on the Move, adaptado para intraday)
  CLUSTER_IDS:
    - CRABEL_RAW_CLEAN
    - NORTHINGTON_RAW_CLEAN
    - CLENOW_RAW_CLEAN

  MECHANISM:
    DESCRIPTION: >
      Períodos de contração de range (baixa volatilidade) acumulam desequilíbrio
      entre compradores e vendedores. A resolução tende a ser direcional e brusca.
    MARKET_LOGIC: >
      Formadores de mercado absorvem fluxo sem mover preço durante a compressão.
      Quando o equilíbrio é rompido por fluxo direcional suficiente, não há
      contrapartida imediata — o preço se move até encontrar novo equilíbrio.
    REGIME_VALIDITY:
      - NORMAL_VOLATILITY
      - EXPANSION_PHASE
      - TREND_DAY (validade máxima)
      - OPENING_PHASE (amplificado)

  SETUP:
    CONDITIONS:
      - Janela de Ouro ativa (10:00–12:30)
      - SESSION_TRANSITION_BLOCK inativo (horário ≥ 10:05)
      - ATR_REGIME_BLOCK inativo (ATR ≤ 1,5x média)
      - LIQ_VOID inativo (volume ≥ 30% da média)
      - VOL_COMP confirmado: ATR atual < 70% ATR médio nas últimas 3+ velas
    Constraints:
      - EC-TIME-02 (GOLDEN_WINDOW_BLOCK)
      - EC-VOL-01 (ATR_REGIME_BLOCK)
      - EC-VOL-02 (HIGH_SPREAD_BLOCK)

  TRIGGER:
    ID:          TRG-01 (VELA1_DIRECTION)
    OBSERVABLE:  Vela 1 fecha com direção clara após período de VOL_COMP
    MEASUREMENT: |
      atr_atual_pre_trigger < atr_medio_20 * 0.70  # compressão confirmada
      AND close_vela1 != open_vela1                  # direção definida

  CONFIRMATION:
    IDS:
      - CNF-01 (VELA2_PHYSICAL_BREAKOUT)
      - CNF-02 (VOLUME_SURGE_CONFIRMATION)
    LOGIC: AND (ambas obrigatórias)
    IMPLEMENTATION: |
      # Compra:
      sinal_compra = (
          close_vela2 > high_vela1 + 0.5
          and volume_vela2 > media_volume_20
      )
      # Venda:
      sinal_venda = (
          close_vela2 < low_vela1 - 0.5
          and volume_vela2 > media_volume_20
      )

  FILTERS:
    HARD:
      - FLT-BLK-01 (NORTHINGTON_BLOCK)
      - FLT-BLK-03 (LATENCY_BLOCK)
    SOFT:
      - FLT-QUA-01 (TIME_DECAY_FILTER) — exigir volume > 1,5x após 11:30

  INVALIDATION:
    CONDITIONS:
      - INV-01 (FALSE_MOMENTUM) — vela2 fecha na direção sem rompimento físico
      - INV-02 (SIGNAL_EXPIRED) — mais de 1 vela sem confirmação
      - INV-03 (REGIME_COLLAPSE) — ATR cruza 1,5x durante monitoramento

  PARAMETERS:
    FIXED:
      ATR_LOOKBACK:          20
      SLIPPAGE_B3:           0.5
      RISCO_PCT:             0.01
      VELA2_MIN_BREAKOUT:    0.5
      VOL_COMP_THRESHOLD:    0.70  # ATR atual < 70% da média
    CALIBRATABLE:
      VOLUME_SURGE_MULT:
        default: 1.0
        min:     0.8
        max:     1.5
        note:    "calibrar via walk-forward, nunca otimizar em IS completo"

  FAILURE_MODES:
    PRIMARY:
      - FM-SIG-01 (FALSE_BREAKOUT) — risco elevado sem volume confirmatório
      - FM-EX-01 (SLIPPAGE_EXPLOSION) — se VOL_SPIKE ocorrer durante expansão
      - FM-REG-01 (REGIME_SHIFT) — TREND_DAY vira ROTATION_DAY intraday
    DETECTION:
      - FM-SIG-01: volume_vela2 < media_volume_20 → risco elevado, aplicar FLT-QUA
      - FM-EX-01: ATR_REGIME_BLOCK automático
      - FM-REG-01: 3 sinais consecutivos com stop atingido → SENTINELA

  EXECUTION:
    DIRECTION:      BOTH (compra e venda)
    ENTRY_TYPE:     MARKET
    STOP_TYPE:      DYNAMIC_ATR
    STOP_FORMULA:   stop_pts = atr_atual + 0.5
    TARGET_TYPE:    ATR_MULTIPLE
    HOLDING_PERIOD: 1–5 velas Renko 8R estimadas

  VALIDATION:
    MINIMUM_TRADES:  30
    WALKFORWARD:     true
    OOS_DEGRADATION: 0.20  # Pardo: degradação máxima 20%
    METRICS:
      - profit_factor > 1.5
      - win_rate > 45%
      - max_drawdown < 15% do capital
      - sharpe_ratio > 1.0 (anualizado, estimado por sessão)

  SEMANTIC_DUPLICATES_CHECKED: false  # A VERIFICAR: AUC_BREAK pode ser duplicata
  NOTES: >
    Verificar sobreposição com AUC_BREAK_001 antes de registrar no Edge Registry.
    VOL_EXP foca em regime de volatilidade; AUC_BREAK foca em estrutura de range.
    Podem ser o mesmo mecanismo — decisão para DeepSeek R1.
```

---

## PROCESSO DE CANONICALIZATION — PASSO A PASSO

### ETAPA 1 — SELEÇÃO DO CLUSTER

```
Input: cluster auditado e aprovado (RAW CLEAN) em /03_CANONICAL_KNOWLEDGE
Ação:  ler cluster completo
Saída: lista de afirmações de edge candidatas
```

### ETAPA 2 — EXTRAÇÃO DE AFIRMAÇÕES DE EDGE

Para cada afirmação de edge no cluster:

```
Pergunta 1: Esta afirmação descreve um mecanismo de mercado mensurável?
  NÃO → descartar (filosofia, não edge)
  SIM → continuar

Pergunta 2: O mecanismo pode ser descrito com observáveis quantitativos?
  NÃO → descartar (edge narrativo sem implementação possível)
  SIM → continuar

Pergunta 3: O mecanismo é específico para o contexto WDO Renko 8R Janela de Ouro?
  NÃO → adaptar ou descartar
  SIM → registrar como candidato
```

### ETAPA 3 — VERIFICAÇÃO DE SEMANTIC DUPLICATION

```
Para cada edge candidato:
  1. Identificar EDGE_TYPE em EDGE_TYPES.md
  2. Verificar se já existe canonical com mesmo EDGE_TYPE
  3. Se existir: comparar MECHANISM e TRIGGER
     - Mesmo mecanismo + mesmo trigger → DUPLICATA → adicionar como SECONDARY_SOURCE
     - Mecanismo similar + trigger diferente → VARIANTE → novo canonical com nota
     - Mecanismo diferente → edge independente → novo canonical
```

### ETAPA 4 — PREENCHIMENTO DO TEMPLATE

```
Preencher TODOS os campos do template.
Campo NOTAS deve registrar:
  - dúvidas sobre o edge
  - potenciais duplicatas não resolvidas
  - itens para validação do DeepSeek R1
```

### ETAPA 5 — REVISÃO DE CONSISTÊNCIA INTERNA

Checklist obrigatório antes de finalizar:

```
[ ] EDGE_ID segue o formato TIPO_CLASSE_NNN?
[ ] EDGE_TYPE existe em EDGE_TYPES.md?
[ ] TRIGGER referenciado existe em SIGNAL_ONTOLOGY.md?
[ ] CONFIRMATION referenciada existe em SIGNAL_ONTOLOGY.md?
[ ] FILTERS referenciados existem em SIGNAL_ONTOLOGY.md?
[ ] INVALIDATION referenciada existe em SIGNAL_ONTOLOGY.md?
[ ] FAILURE_MODES referenciados existem em FAILURE_MODES.md?
[ ] EXECUTION_CONSTRAINTS aplicadas existem em EXECUTION_CONSTRAINTS.md?
[ ] PARAMETERS.FIXED inclui ATR_LOOKBACK=20, SLIPPAGE_B3=0.5, RISCO_PCT=0.01?
[ ] STOP_FORMULA usa ATR dinâmico + 0.5 (nunca stop fixo)?
[ ] SEMANTIC_DUPLICATES_CHECKED = true?
[ ] OOS_DEGRADATION = 0.20 (Pardo)?
[ ] WALKFORWARD = true?
```

### ETAPA 6 — STATUS E DESTINO

```
STATUS = DRAFT → arquivo em /04_CANONICAL_KNOWLEDGE/drafts/
STATUS = VALIDATED (após DeepSeek R1) → arquivo em /04_CANONICAL_KNOWLEDGE/
STATUS = DEPRECATED → arquivo em /04_CANONICAL_KNOWLEDGE/deprecated/
```

---

## CONVENÇÃO DE NOMENCLATURA — EDGE_ID

```
Formato: {TIPO}_{CLASSE}_{NNN}

TIPO:    abreviação do EDGE_TYPE (3-7 chars)
         VOL_EXP, VOL_COMP, MOM_CONT, MOM_REV, AUC_IMBAL, AUC_FAIL,
         AUC_BRK, TIME_OPEN, TIME_DEC, LIQ_SURG, MR_INTRA

CLASSE:  abreviação da CLASSE (3 chars)
         VST (VOLATILITY_STRUCTURE)
         MDR (MOMENTUM_DIRECTIONAL)
         ACS (AUCTION_STRUCTURE)
         TMS (TIME_STRUCTURAL)
         LQP (LIQUIDITY_PARTICIPATION)
         MVR (MEAN_REVERSION)

NNN:     sequencial 3 dígitos (001, 002, ...)

Exemplos:
  VOL_EXP_VST_001   → primeiro edge de Volatility Expansion
  MOM_CONT_MDR_001  → primeiro edge de Momentum Continuation
  AUC_FAIL_ACS_001  → primeiro edge de Failed Auction
```

---

## ANTI-PADRÕES — O QUE NÃO FAZER

```
✘ Canonicalizar sem verificar semantic duplication
✘ Deixar campos vazios ("a definir") — edge incompleto não vai para registry
✘ Usar parâmetros diferentes dos fixos do sistema sem justificativa formal
✘ Misturar dois autores num único MECHANISM sem verificar se é o mesmo edge
✘ Criar canonical para afirmação filosófica sem observável quantitativo
✘ STATUS = VALIDATED sem revisão do DeepSeek R1
✘ Omitir FAILURE_MODES — todo edge tem pelo menos um
✘ Esquecer SEMANTIC_DUPLICATES_CHECKED = true antes de submeter ao registry
```

---

## MAPA DE CANONICALIZATION — CLUSTERS APROVADOS

Referência para início do processo após validação desta spec:

| Cluster | Edges Candidatos Prováveis | Prioridade |
|---|---|---|
| HARRIS v2 | MOM_CONT, FALSE_BREAKOUT (invalida), AUC_BREAK | 1 |
| CRABEL | VOL_EXP, VOL_COMP, AUC_BREAK | 1 |
| NORTHINGTON | VOL_SPIKE (filter), TIME_OPEN, TIME_DECAY, ATR_REGIME | 1 |
| VINCE | Position sizing (não é edge — vai para EXECUTION_CONSTRAINTS) | 1 |
| PARDO | Validação (não é edge — vai para VALIDATION_FRAMEWORK) | 2 |
| DALTON | AUC_IMBAL, AUC_FAIL, DEAD_MARKET | 2 |
| DONNELLY | MOM_REVERSAL, AUC_FAIL, LIQ_SURGE | 2 |
| KLEPPMANN | LIQ_VOID, LIQ_SURGE, SPREAD_EXPANSION | 2 |
| CLENOW | MOM_CONT (corrobora Harris), VOL_EXP (corrobora Crabel), MR_INTRA | 2 |
| CARVER | MR_INTRA, execution cost (→ CONSTRAINTS), robustness (→ VALIDATION) | 3 |
| THARP | Position sizing / psicologia (→ EXECUTION_CONSTRAINTS, não edge direto) | 3 |

**Nota:** Vince, Pardo e Tharp provavelmente não geram Canonical Edges —
seus clusters alimentam EXECUTION_CONSTRAINTS e VALIDATION_FRAMEWORK.
Confirmar na canonicalization de cada um.

---

## ALERTAS PARA VALIDAÇÃO DeepSeek R1

- [ ] Verificar se o template está completo ou se faltam campos críticos
- [ ] VOL_EXP_001 exemplo: confirmar se AUC_BREAK é duplicata ou edge independente
- [ ] Convenção de nomenclatura TIPO_CLASSE_NNN: validar se é suficientemente expressiva
- [ ] ETAPA 3 (semantic duplication): o critério "mesmo mecanismo + mesmo trigger" é suficiente?
- [ ] Mapa de canonicalization: confirmar que Vince/Pardo/Tharp não geram edges diretos
- [ ] STATUS DRAFT vs. VALIDATED: definir critérios exatos para promoção de DRAFT para VALIDATED
- [ ] Confirmar se /04_CANONICAL_KNOWLEDGE é a pasta correta ou se o documento de transição usa nomenclatura diferente

---

*Arquivo gerado para validação externa. Classificação final: exclusividade DeepSeek R1 com DeepThink.*
