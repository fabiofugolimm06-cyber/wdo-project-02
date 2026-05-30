# FAILURE_MODES.md
# WDO-EVOLVED-QUANT — Modos de Falha de Edge
# Ativo: WDO (Mini Dólar B3) | Gráfico: Renko 8R | Janela: 10:00–12:30
# Versão: 1.0 | Status: AGUARDANDO VALIDAÇÃO DeepSeek R1

---

## DEFINIÇÃO FORMAL

Um **failure mode** é um mecanismo causal pelo qual um edge perde sua
assimetria estatística — temporária ou permanentemente.

Distinguir o tipo de falha é crítico:
- Falha **estrutural**: o edge morreu permanentemente (regime shift).
- Falha **episódica**: o edge falhou neste trade específico (condição adversa).
- Falha **de execução**: o edge existe mas não foi capturado (latência, slippage).
- Falha **de modelo**: o edge nunca existiu — era overfitting.

---

## CATÁLOGO DE FAILURE MODES

---

### FM-001 | SLIPPAGE_EXPLOSION

**Tipo:** Falha de execução

**Definição:** O custo real de execução (spread + slippage de mercado)
excede o custo modelado, consumindo o edge antes de se materializar.

**Mecanismo:** Em condições de baixa liquidez ou volatilidade elevada,
a diferença entre o preço do sinal e o preço real de execução
ultrapassa o threshold de viabilidade do trade.

**Condição de ocorrência:**
- Spread bid-ask > 0,5 ponto (acima do slippage institucional modelado)
- Livro de ofertas fino no momento da entrada
- Execução via NTSL/Profit com latência > 1 vela

**Threshold de bloqueio WDO:**
- Slippage modelado: 0,5 ponto (fixo, institucional B3)
- Se spread observado > 1,0 ponto: sinal deve ser descartado

**Edge types mais vulneráveis:** ET-LIQ-01, ET-MOM-02, ET-VOL-01

**Detecção:** Comparação sistemática entre preço do sinal e preço de fill.
Degradação > 20% na expectativa ajustada por slippage real vs. modelado
indica problema estrutural de execução.

**Mitigação WDO:** Slippage de 0,5 ponto sempre incluído no cálculo
de position sizing (stop_real = ATR + 0,5).

---

### FM-002 | FALSE_BREAKOUT

**Tipo:** Falha episódica

**Definição:** O preço rompe um nível estrutural, ativa o sinal de entrada,
e reverte imediatamente sem desenvolver movimento direcional.

**Mecanismo:** Rompimento gerado por stop hunt institucional ou ausência
de continuidade de fluxo. O nível é testado mas não há participantes
dispostos a dar continuidade ao movimento após o rompimento.

**Condição de ocorrência:**
- Volume no rompimento abaixo da média de 20 velas
- Ausência de confirmação de agressão via Times & Trades
- Rompimento sem retest e continuidade (vela de reversão imediata)
- Regime de mercado ROTATION_DAY ou DEAD_LIQUIDITY

**Threshold de bloqueio WDO:**
- Confirmação Vela 2 obrigatória: close_vela2 > high_vela1 + 0,5
- Volume da Vela 2 < média 20 velas → sinal DESCARTADO

**Edge types mais vulneráveis:** ET-MOM-02, ET-MOM-01, ET-VOL-01

**Detecção:** Taxa de false breakout > 40% em regime específico indica
que o edge perdeu validade naquele regime — requer regime discriminador.

**Mitigação WDO:** Confirmação obrigatória de Vela 2 com rompimento
físico ≥ 0,5 ponto é a defesa primária contra este failure mode.

---

### FM-003 | VOLATILITY_SPIKE

**Tipo:** Falha episódica / Estrutural temporária

**Definição:** Evento de volatilidade extrema torna os parâmetros
de risco do modelo inválidos — stop baseado em ATR normal é insuficiente
para o regime atual.

**Mecanismo:** Choque de volatilidade (dados macro, evento geopolítico,
crise de liquidez) cria movimento > 3x ATR médio em uma única vela.
O stop dinâmico, calibrado para regime normal, é ativado prematuramente.

**Condição de ocorrência:**
- ATR atual > 1,5x ATR médio das últimas 20 velas (Filtro Northington)
- Evento macro não precificado (payroll, FOMC, CPI, BCB)
- Gap de abertura > 2x ATR médio

**Threshold de bloqueio WDO:**
- Filtro Northington: se ATR_atual > ATR_médio × 1,5 → BLOQUEIO TOTAL
- Sistema entra em modo Sentinela (zero ordens)

**Edge types mais vulneráveis:** ET-VOL-01, ET-AUC-01, ET-REV-01

**Detecção:** Monitoramento contínuo do ratio ATR_atual/ATR_médio.
Ratio > 1,5 → bloqueio imediato, sem exceções.

**Mitigação WDO:** Filtro Northington é a defesa estrutural primária.
Não há override — nem "parece bom demais para não entrar".

---

### FM-004 | LATENCY_DECAY

**Tipo:** Falha de execução

**Definição:** O sinal perde validade durante o tempo de transmissão
entre geração (Python) e execução (Profit One/NTSL), tornando o preço
de entrada inviável.

**Mecanismo:** Em infraestrutura retail (100–500ms), movimentos rápidos
do WDO podem tornar o preço do sinal obsoleto antes da ordem chegar
à bolsa. O edge existe no momento do sinal mas não no momento da execução.

**Condição de ocorrência:**
- Latência de rede > 200ms em período de alta volatilidade
- Vela de Renko 8R se fecha antes do fill ser confirmado
- Movimento de > 1 ponto entre sinal e fill

**Threshold de bloqueio WDO:**
- Latência máxima: 1 vela (regra absoluta)
- Se velas_desde_sinal > 1 → ordem cancelada automaticamente

**Edge types mais vulneráveis:** ET-LIQ-01, ET-VOL-03, ET-MOM-01

**Detecção:** Log obrigatório de timestamp do sinal vs. timestamp do fill.
Diferença > 1 vela → ordem cancelada e registrada como LATENCY_CANCEL.

**Mitigação WDO:** Cancelamento automático por latência implementado
no Automator. Não há execução de sinais velhos.

---

### FM-005 | LIQUIDITY_VOID

**Tipo:** Falha episódica / Estrutural

**Definição:** Ausência de contraparte suficiente no momento da execução
— o mercado não tem liquidez para absorver a ordem ao preço esperado.

**Mecanismo:** Em horários de baixa participação ou após eventos de
choque, o book de ofertas se esvazia em um ou ambos os lados. Ordens
a mercado criam slippage extremo. Ordens limitadas não são executadas.

**Condição de ocorrência:**
- Volume total do período < 50% da média histórica do horário
- Spread bid-ask > 1 ponto
- Regime DEAD_LIQUIDITY ou MIDDAY_DECAY ativo

**Threshold de bloqueio WDO:**
- Volume da vela de sinal < 50% da média de 20 velas → DESCARTADO
- Regime DEAD_LIQUIDITY → modo Sentinela

**Edge types mais vulneráveis:** ET-LIQ-01, ET-VOL-03, ET-MOM-01

**Detecção:** Monitoramento de volume relativo. Queda persistente de
volume indica regime de liquidez degradada — não é anomalia pontual.

**Mitigação WDO:** Janela de Ouro 10:00–12:30 é parcialmente uma defesa
contra este failure mode — concentra trades no período de maior liquidez.

---

### FM-006 | SPREAD_EXPANSION

**Tipo:** Falha de execução

**Definição:** Expansão anormal do spread bid-ask aumenta o custo efetivo
de entrada além do modelado, consumindo o edge antes de materializar lucro.

**Mecanismo:** Em transições de sessão, eventos de incerteza ou baixa
participação, market makers aumentam o spread para se proteger do risco
de fluxo informado. O trader retail paga spread expandido na entrada
e na saída.

**Condição de ocorrência:**
- Transições de sessão (abertura, pré-NY)
- Eventos macro agendados (FOMC, payroll, BCB)
- Regime de baixa liquidez ou choque de volatilidade

**Threshold de bloqueio WDO:**
- Spread > 1,0 ponto → entrada bloqueada
- Verificação obrigatória de spread antes de qualquer ordem

**Edge types mais vulneráveis:** ET-TMP-02, ET-AUC-02, ET-VOL-01

**Detecção:** Comparação de spread observado vs. spread histórico médio
do mesmo horário. Desvio > 2x a norma histórica → bloqueio preventivo.

**Mitigação WDO:** Inclusão de 0,5 ponto de slippage institucional em
todos os cálculos é a proteção mínima. Spread > 1,0 ponto invalida
o cálculo de viabilidade do trade.

---

### FM-007 | REGIME_SHIFT

**Tipo:** Falha estrutural

**Definição:** O regime de mercado muda de forma que o edge deixa de
ter validade estatística no novo regime — não é falha episódica, é
invalidação estrutural.

**Mecanismo:** Edges são válidos em regimes específicos. Um edge de
momentum válido em TREND_DAY é inválido em ROTATION_DAY. Um edge de
expansão válido em NORMAL_VOLATILITY é perigoso em PANIC_PHASE.
Quando o regime muda, o edge morre — até o regime favorável retornar.

**Condição de ocorrência:**
- Mudança de regime sem atualização do discriminador de regime
- Aplicação de edge de momentum em mercado rotacional
- Aplicação de edge de reversão em mercado de tendência forte

**Threshold de bloqueio WDO:**
- Identificação de regime é pré-requisito para qualquer sinal
- Ver MARKET_REGIMES.md para definição formal de cada regime

**Edge types mais vulneráveis:** Todos — especialmente ET-REV-01 vs.
ET-MOM-01 (mutuamente exclusivos por regime)

**Detecção:** Degradação sistemática de performance em período recente
sem mudança nos parâmetros do sistema indica regime shift. Auditoria
Pardo (degradação OOS > 20%) é o gatilho formal de investigação.

**Mitigação WDO:** MARKET_REGIMES.md define os estados e os edges
válidos em cada um. Discriminador de regime é componente obrigatório
do pipeline antes de qualquer geração de sinal.

---

### FM-008 | OVERFIT_DECAY

**Tipo:** Falha de modelo

**Definição:** O edge nunca existiu como assimetria real — era padrão
espúrio identificado em dados históricos sem validade fora da amostra.

**Mecanismo:** Otimização excessiva de parâmetros em dados históricos
cria edge aparente que não se sustenta em dados novos. O sistema parece
funcionar em backtest e falha em live trading não por mudança de regime,
mas porque o edge foi inventado pelo processo de otimização.

**Condição de ocorrência:**
- Parâmetros otimizados em janela histórica sem walk-forward
- Número de parâmetros livres desproporcional ao tamanho da amostra
- Edge identificado em amostra única sem replicação out-of-sample

**Threshold de bloqueio WDO:**
- Critério Pardo: degradação OOS < 20% é o único threshold aceitável
- Edge com degradação OOS > 20% → descartado como OVERFIT

**Edge types mais vulneráveis:** Todos igualmente

**Detecção:** Walk-forward obrigatório no VALIDATION FRAMEWORK.
Comparação IS vs. OOS com critério Pardo de degradação < 20%.

**Mitigação WDO:** Proibição de otimização antes do VALIDATION FRAMEWORK
estar implementado. Nenhum parâmetro é "otimizado" — são derivados das
fontes primárias (clusters auditados).

---

### FM-009 | QUEUE_POSITION_UNCERTAINTY

**Tipo:** Falha de execução (retail-específica)

**Definição:** Em infraestrutura retail sem colocation, a posição na fila
de ordens é incerta — o sistema não sabe se será executado antes ou
depois dos participantes institucionais.

**Mecanismo:** Ordens chegam à B3 com latência de 100–500ms. Participantes
com colocation (< 1ms) têm prioridade de fila. Em movimentos rápidos,
o retail é executado em preços piores ou não é executado quando a
liquidez se esgota antes da chegada da ordem.

**Condição de ocorrência:**
- Qualquer trade em período de alta volatilidade
- Especialmente crítico para ET-LIQ-01 (depende de timing preciso)
- Piora em abertura e transições de sessão

**Threshold de bloqueio WDO:**
- Este failure mode é estrutural para infraestrutura retail — não tem
  threshold de bloqueio isolado. É mitigado por design sistêmico.

**Edge types mais vulneráveis:** ET-LIQ-01 (mais crítico),
ET-VOL-03, ET-MOM-02

**Detecção:** Análise estatística de slippage real vs. modelado ao longo
do tempo. Slippage médio > 1,0 ponto indica queue position adversa crônica.

**Mitigação WDO:** Seleção de edges menos dependentes de execução
milimétrica. ET-LIQ-01 é o edge mais arriscado neste contexto —
requer confirmação adicional antes de uso em produção.

---

## TABELA DE REFERÊNCIA RÁPIDA

| ID     | Nome                    | Tipo               | Mitigação Primária WDO              |
|--------|-------------------------|--------------------|--------------------------------------|
| FM-001 | SLIPPAGE_EXPLOSION      | Execução           | Slippage 0,5pt no sizing             |
| FM-002 | FALSE_BREAKOUT          | Episódica          | Confirmação Vela 2 obrigatória       |
| FM-003 | VOLATILITY_SPIKE        | Episódica          | Filtro Northington (1,5x ATR)        |
| FM-004 | LATENCY_DECAY           | Execução           | Cancel automático > 1 vela           |
| FM-005 | LIQUIDITY_VOID          | Episódica          | Janela de Ouro 10:00–12:30           |
| FM-006 | SPREAD_EXPANSION        | Execução           | Bloqueio se spread > 1,0pt           |
| FM-007 | REGIME_SHIFT            | Estrutural         | Discriminador de regime (MARKET_REGIMES.md) |
| FM-008 | OVERFIT_DECAY           | Modelo             | Walk-forward Pardo (OOS < 20%)       |
| FM-009 | QUEUE_POSITION_UNCERTAINTY | Execução retail | Edges não dependentes de timing fino |

---

## NOTAS DE AUDITORIA

- Gerado por: Claude Sonnet (assistente)
- Validação pendente: DeepSeek R1 com DeepThink ativado
- Referência cruzada obrigatória: EDGE_TYPES.md, MARKET_REGIMES.md,
  EXECUTION_CONSTRAINTS.md
