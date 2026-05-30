# SIGNAL_ONTOLOGY.md
# WDO-EVOLVED-QUANT | /03_EDGE_TAXONOMY
# Versão: 1.0 | Status: AGUARDANDO VALIDAÇÃO DeepSeek R1

---

## POR QUE ONTOLOGIA DE SINAL É CRÍTICA

Sem definições formais e exclusivas, os seguintes problemas emergem:

1. **Semantic collision**: "setup" e "trigger" são tratados como sinônimos → lógica de código ambígua
2. **Double-counting**: o mesmo observável é tratado como trigger E confirmação → sinal circular
3. **Filter confusion**: filtros de regime são confundidos com confirmações de sinal → arquitetura incorreta
4. **Invalidation gap**: ausência de definição formal de invalidação → sistema nunca descarta sinal pendente

Esta ontologia define **categorias mutuamente exclusivas** para cada componente de um sinal.

---

## DEFINIÇÕES FORMAIS

---

### 1. SETUP

**Definição:**
Conjunto de condições de **contexto e regime** que precisam estar presentes para que
uma oportunidade de edge seja possível. O setup não gera entrada. Ele qualifica o ambiente.

**Características:**
- Precede o trigger temporalmente
- É avaliado de forma contínua (a cada nova vela)
- Sua ausência invalida qualquer trigger subsequente
- É composto por condições de regime (MARKET_REGIMES) e constraints (EXECUTION_CONSTRAINTS)

**Componentes do setup no WDO-EVOLVED-QUANT:**
```
SETUP válido quando TODOS os seguintes são verdadeiros:
  ✔ Janela de Ouro ativa (10:00–12:30)
  ✔ SESSION_TRANSITION_BLOCK inativo (horário ≥ 10:05)
  ✔ PRE_CLOSE_BLOCK inativo (horário ≤ 12:15)
  ✔ ATR_REGIME_BLOCK inativo (ATR atual ≤ 1,5x ATR médio)
  ✔ LIQ_VOID inativo (volume ≥ 30% da média)
  ✔ Regime identificado (TREND_DAY ou ROTATION_DAY ou OPENING_IMBALANCE_DAY)
  ✔ Capital suficiente para ≥ 1 contrato (EC-SIZE-02)
```

**Relação com outros componentes:**
```
SETUP → habilita monitoramento de TRIGGER
SETUP ausente → TRIGGER é ignorado, independente do que ocorre no preço
```

**Pergunta-teste:** "O ambiente está correto para que um edge possa existir agora?"

---

### 2. TRIGGER

**Definição:**
O evento de mercado **específico e discreto** que sinaliza o início potencial de um edge.
O trigger é o primeiro evento observável que indica que algo pode estar acontecendo.

**Características:**
- É um evento pontual (ocorre em uma vela específica)
- É necessário mas NÃO suficiente para entrada
- Sempre requer CONFIRMATION antes de gerar ordem
- Exige SETUP válido para ser monitorado

**Triggers no WDO-EVOLVED-QUANT:**

| ID | Trigger | Edge Associado | Observável |
|---|---|---|---|
| TRG-01 | VELA1_DIRECTION | MOM_CONT | Vela 1 fecha com direção clara (alta ou baixa) |
| TRG-02 | RANGE_COMPRESSION | VOL_EXP | ATR atual < 70% ATR médio por 3+ velas consecutivas |
| TRG-03 | RANGE_BREAK_CANDIDATE | AUC_BREAK | Preço toca extremo de range definido |
| TRG-04 | EXTREME_TEST | AUC_FAIL / MOM_REVERSAL | Preço testa máxima/mínima do range pela segunda vez |
| TRG-05 | OPENING_DIRECTION | TIME_OPEN / AUC_IMBAL | Direção das primeiras 3 velas após 10:05 é consistente |
| TRG-06 | EXTENSION_DETECTED | MR_INTRA | Preço > VWAP + 2x ATR ou < VWAP - 2x ATR |

**Relação com outros componentes:**
```
SETUP válido + TRIGGER detectado → ativar monitoramento de CONFIRMATION
TRIGGER sem SETUP → ignorado completamente
```

**Pergunta-teste:** "Algo específico aconteceu no mercado que merece atenção?"

---

### 3. CONFIRMATION

**Definição:**
A evidência **adicional e independente** que eleva a probabilidade do edge de "possível"
para "suficientemente provável para execução". A confirmation é o evento que converte
trigger em sinal de entrada.

**Características:**
- É observável APÓS o trigger (nunca simultâneo)
- Deve ser **independente** do trigger (não pode ser derivado do mesmo dado)
- Sua presença, combinada com trigger válido, gera sinal de entrada
- Ausência da confirmation → trigger descartado, aguardar próximo

**Confirmações no WDO-EVOLVED-QUANT:**

| ID | Confirmation | Trigger Associado | Observável |
|---|---|---|---|
| CNF-01 | VELA2_PHYSICAL_BREAKOUT | TRG-01 (VELA1_DIRECTION) | close_vela2 > high_vela1 + 0,5pt (compra) ou close_vela2 < low_vela1 - 0,5pt (venda) |
| CNF-02 | VOLUME_SURGE_CONFIRMATION | TRG-01, TRG-03, TRG-05 | Volume vela de confirmação > média volume 20 velas |
| CNF-03 | BREAKOUT_CLOSE_OUTSIDE | TRG-03 (RANGE_BREAK) | Fechamento fora do range em ≥ 1,0 ponto (não apenas toque) |
| CNF-04 | REJECTION_CANDLE | TRG-04 (EXTREME_TEST) | Vela que testou extremo fecha de volta no interior do range |
| CNF-05 | EXPANSION_CANDLE | TRG-02 (RANGE_COMPRESSION) | Vela de rompimento com range > 1,5x range médio das últimas K velas |

**CONFIRMAÇÃO PRINCIPAL OBRIGATÓRIA — MOM_CONT:**
```python
# CNF-01: Vela 2 confirma Vela 1
sinal_compra  = close_vela2 > (high_vela1 + 0.5)
sinal_venda   = close_vela2 < (low_vela1 - 0.5)

# CNF-02: Volume confirma
volume_ok = volume_vela2 > media_volume_20_velas

# Sinal VÁLIDO somente quando AMBAS as confirmações são verdadeiras:
sinal_valido = (sinal_compra or sinal_venda) and volume_ok
```

**Relação com outros componentes:**
```
SETUP válido + TRIGGER ativo + CONFIRMATION presente → SINAL DE ENTRADA gerado
Qualquer um ausente → sem sinal
```

**Pergunta-teste:** "A evidência é suficiente para agir agora?"

---

### 4. FILTER

**Definição:**
Condição de **contexto adicional** que, quando ativa, reduz ou aumenta a confiança
no sinal gerado. Diferente do SETUP (que é pré-requisito), o filter é graduado —
ele pondera a qualidade do sinal, não sua validade binária.

**Tipos de filter:**

#### FILTER BLOQUEADOR (HARD FILTER)
Quando ativo, cancela o sinal independente de confirmação.
Funcionalmente equivale a um requisito de SETUP que pode ser ativado mid-signal.

| ID | Filter | Condição de Bloqueio |
|---|---|---|
| FLT-BLK-01 | NORTHINGTON_BLOCK | ATR_atual > ATR_medio_20 × 1,5 |
| FLT-BLK-02 | LIQUIDITY_VOID_BLOCK | Volume < 30% da média |
| FLT-BLK-03 | LATENCY_BLOCK | Velas desde sinal > 1 |
| FLT-BLK-04 | REGIME_MISMATCH_BLOCK | Edge de TREND_DAY gerado em ROTATION_DAY confirmado |

#### FILTER DE QUALIDADE (SOFT FILTER)
Quando ativo, não bloqueia mas sinaliza sinal de menor qualidade.
Pode ser usado para reduzir tamanho de posição ou exigir confirmação adicional.

| ID | Filter | Condição de Degradação |
|---|---|---|
| FLT-QUA-01 | TIME_DECAY_FILTER | Horário > 11:30 — exigir volume > 1,5x média |
| FLT-QUA-02 | SECOND_SIGNAL_FILTER | Mesmo edge gerado 2x no mesmo dia — reduzir confiança |
| FLT-QUA-03 | LOW_VOLUME_CAUTION | Volume entre 50% e 80% da média — sinal de qualidade reduzida |

**Relação com outros componentes:**
```
Sinal gerado (SETUP + TRIGGER + CONFIRMATION) → aplicar FILTERS
FLT-BLK ativo → cancelar sinal
FLT-QUA ativo → sinal de menor qualidade (documentar, não bloquear)
```

**Pergunta-teste:** "O contexto adicional aumenta ou diminui a confiança no sinal?"

---

### 5. INVALIDATION

**Definição:**
Condição que, quando detectada **após a geração do trigger mas antes da execução**,
cancela o sinal e reinicia o ciclo de monitoramento.

**Características:**
- Ocorre APÓS o trigger, ANTES da execução
- Diferente do FILTER: a invalidação não é sobre qualidade, é sobre impossibilidade do edge
- Diferente do FAILURE MODE: a invalidation previne entrada; failure mode ocorre durante o trade
- Uma vez invalidado, o sinal é descartado — não há "reativação" do mesmo sinal

**Invalidações no WDO-EVOLVED-QUANT:**

| ID | Invalidação | Trigger Cancelado | Condição |
|---|---|---|---|
| INV-01 | FALSE_MOMENTUM | TRG-01 (VELA1_DIRECTION) | Vela 2 fecha na mesma direção mas NÃO rompe extremo em ≥ 0,5pt |
| INV-02 | SIGNAL_EXPIRED | Qualquer | Mais de 1 vela se passou desde o trigger sem confirmação |
| INV-03 | REGIME_COLLAPSE | Qualquer | ATR cruza 1,5x durante monitoramento do sinal |
| INV-04 | DIRECTION_REVERSAL | TRG-01, TRG-05 | Preço reverte para o lado oposto antes da confirmação |
| INV-05 | VOLUME_COLLAPSE | TRG-01, TRG-03 | Volume da vela de confirmação < 50% da média (sem LIQ_VOID total) |

**Implementação INV-01 (crítica):**
```python
# Fundamento Northington: exaustão disfarçada
# Trigger: Vela 1 sobe (TRG-01)
# Monitorando Vela 2:

if close_vela2 > close_vela1:          # mesma direção
    if close_vela2 <= high_vela1 + 0.5: # mas SEM rompimento físico
        log.warning(
            "[SIGNAL] INV-01 | FALSE_MOMENTUM | "
            "Vela2 fecha na direção mas sem rompimento físico ≥ 0,5pt | "
            "Sinal descartado"
        )
        return None  # INVALIDADO
```

**Relação com outros componentes:**
```
TRIGGER ativo → monitorar INVALIDATION e CONFIRMATION simultaneamente
INVALIDATION detectada → descartar sinal, voltar para monitoramento de SETUP
CONFIRMATION detectada (sem INVALIDATION) → gerar SINAL DE ENTRADA
```

**Pergunta-teste:** "O edge ainda pode existir ou o contexto que o criou desapareceu?"

---

## CICLO COMPLETO DE UM SINAL

```
┌─────────────────────────────────────────────────────────────────┐
│                        CICLO DE SINAL                           │
└─────────────────────────────────────────────────────────────────┘

[1] AVALIAÇÃO DE SETUP (contínua, toda vela)
    ↓ SETUP inválido → aguardar (loop)
    ↓ SETUP válido ↓

[2] MONITORAMENTO DE TRIGGER (toda vela, com SETUP válido)
    ↓ Nenhum trigger → aguardar (loop)
    ↓ Trigger detectado ↓

[3] AVALIAÇÃO SIMULTÂNEA: INVALIDATION vs. CONFIRMATION
    ↓ INVALIDATION detectada → descartar, voltar para [2]
    ↓ CONFIRMATION detectada (sem INVALIDATION) ↓

[4] APLICAÇÃO DE FILTERS
    ↓ FLT-BLK ativo → cancelar, voltar para [2]
    ↓ FLT-QUA ativo → registrar qualidade reduzida, continuar
    ↓ Nenhum filtro bloqueador ↓

[5] GERAÇÃO DE SINAL DE ENTRADA
    → encaminhar para RiskManager
    → RiskManager aplica EC-SIZE-01, EC-SIZE-02, EC-SIZE-03
    → RiskManager calcula n_contratos e stop_dinamico
    → Automator executa (sujeito a EC-LAT-01)

[6] MONITORAMENTO DE TRADE (após execução)
    → Stop dinâmico recalculado a cada vela (EC-SIG-02)
    → Verificar FM-SIG-02 (MOMENTUM_STALL)
    → Encerrar em 12:15 (PRE_CLOSE_BLOCK) se ainda aberto
```

---

## SEPARAÇÃO DE RESPONSABILIDADES POR MÓDULO

| Componente Ontológico | Módulo Responsável | Arquivo |
|---|---|---|
| SETUP | RiskManager | risk_manager.py |
| TRIGGER | SignalGenerator | signal_generator.py |
| CONFIRMATION | SignalGenerator | signal_generator.py |
| FILTER (BLK) | RiskManager | risk_manager.py |
| FILTER (QUA) | SignalGenerator | signal_generator.py |
| INVALIDATION | SignalGenerator | signal_generator.py |
| Execução | Automator | automator.py |

**Regra de ouro:**
- **SignalGenerator** não conhece capital, contratos ou sizing
- **RiskManager** não conhece lógica de preço ou padrões de vela
- **Automator** não conhece lógica de sinal ou risco — só executa ordens autorizadas

---

## PROTOCOLO DE LOG POR COMPONENTE

```
[SETUP]   Janela de Ouro: 10:32 ✓ | ATR: 8.2/12.3 (67%) ✓ | Volume OK ✓ | Setup VÁLIDO
[TRIGGER] TRG-01 detectado | Vela1: H=5342.0 L=5334.0 | Direção: ALTA
[SIGNAL]  CNF-01 monitorando | Vela2 fechando...
[SIGNAL]  CNF-01 CONFIRMADO | C=5342.8 > H_v1+0.5=5342.5 ✓
[SIGNAL]  CNF-02 CONFIRMADO | Vol=1340 > Med20=980 ✓
[FILTER]  FLT-QUA-01 inativo (horário 10:32) | Qualidade: ALTA
[SIGNAL]  SINAL COMPRA VÁLIDO → encaminhando para RiskManager
[RISK]    Sizing: Capital=50000 | ATR=8.2 | Stop=8.7pts | Contratos=math.floor(500/87)=5
[RISK]    AUTORIZADO | 5 contratos | Stop: 8.7pts | Risco: R$435.00
[AUTOMATOR] Ordem enviada | 5 contratos COMPRA | Preço mercado
[AUTOMATOR] Confirmação em 0 velas | Execução: OK
```

---

## ALERTAS PARA VALIDAÇÃO DeepSeek R1

- [ ] SETUP vs. FILTER (BLK): verificar se a distinção é útil ou se devem ser unificados
- [ ] INV-05 VOLUME_COLLAPSE: threshold 50% é arbitrário — validar contra dados WDO
- [ ] FLT-QUA-02 SECOND_SIGNAL_FILTER: definir quantas operações por dia são permitidas
- [ ] Ciclo [3]: confirmação e invalidação simultâneas — definir precedência quando ambas ocorrem na mesma vela
- [ ] Separação de responsabilidades: verificar se RiskManager fazendo SETUP é a melhor arquitetura ou se deve haver módulo dedicado de ContextManager

---

*Arquivo gerado para validação externa. Classificação final: exclusividade DeepSeek R1 com DeepThink.*
