# MARKET_REGIMES.md
# WDO-EVOLVED-QUANT | /03_EDGE_TAXONOMY
# Versão: 1.0 | Status: AGUARDANDO VALIDAÇÃO DeepSeek R1

---

## DEFINIÇÃO OPERACIONAL DE REGIME

Regime é o **estado estrutural do mercado** que determina quais edges são válidos,
quais failure modes são mais prováveis, e qual é a postura correta do sistema.

Regime **não é** previsão de direção.
Regime **é** classificação do ambiente de execução no momento presente.

O sistema opera em um único regime por vez.
A transição entre regimes pode ocorrer intraday.

---

## HIERARQUIA DE CLASSIFICAÇÃO

```
DIMENSÃO DE VOLATILIDADE  (primária — define operabilidade)
  └── DIMENSÃO DIRECIONAL  (secundária — define estratégia dentro do regime operável)
        └── DIMENSÃO TEMPORAL  (terciária — define contexto dentro da sessão)
```

O regime completo é a combinação das três dimensões.
Exemplo: `NORMAL_VOLATILITY + TREND_DAY + OPENING_PHASE`

---

## DIMENSÃO 1 — VOLATILIDADE

Define se o sistema pode operar e com qual custo esperado.

---

### REG-VOL-01 — LOW_VOLATILITY

**Definição:**
ATR atual < 70% do ATR médio das últimas 20 velas.
Mercado em compressão. Liquidez presente mas movimento direcional reduzido.

**Características:**
- Range de velas estreito
- Slippage dentro do parâmetro normal (0,5 ponto)
- Precede frequentemente VOL_EXP (Crabel: narrow range antes de expansão)

**Edges válidos:**
- VOL_COMP (identificação de estado — preparar para VOL_EXP)
- AUC_BREAK (aguardar rompimento do range comprimido)
- Nenhum sinal direcional até confirmação de rompimento

**Edges inválidos:**
- MOM_CONT (não há momentum para continuar)
- MR_INTRA (range estreito não oferece extensão para reverter)

**Postura do sistema:**
- MODO ALERTA: monitorar sinais de VOL_EXP
- Reduzir frequência de ordens, aumentar threshold de confirmação

**Detecção:**
```
ATR_atual < ATR_medio_20 × 0.70  →  LOW_VOLATILITY confirmado
```

---

### REG-VOL-02 — NORMAL_VOLATILITY

**Definição:**
ATR atual entre 70% e 150% do ATR médio das últimas 20 velas.
Regime operacional padrão do sistema. Todos os parâmetros calibrados para este estado.

**Características:**
- Slippage dentro do parâmetro nominal (0,5 ponto confiável)
- Liquidez adequada para execução retail
- Edges direcionais com probabilidade positiva esperada

**Edges válidos:**
- Todos os edges da taxonomia, sujeito às condições de cada um
- MOM_CONT: validade máxima em TREND_DAY dentro deste regime
- VOL_EXP: válido quando preceded by LOW_VOLATILITY
- AUC_IMBAL, AUC_BREAK: válidos

**Postura do sistema:**
- MODO OPERACIONAL: sistema completo ativo
- Parâmetros nominais sem ajuste

**Detecção:**
```
ATR_medio_20 × 0.70 ≤ ATR_atual ≤ ATR_medio_20 × 1.50  →  NORMAL_VOLATILITY
```

---

### REG-VOL-03 — EXPANSION_PHASE

**Definição:**
ATR atual entre 100% e 150% do ATR médio (zona de expansão — próxima ao limite Northington).
Volatilidade acima da média mas ainda dentro do regime operável.

**Características:**
- Slippage pode ser levemente superior ao nominal
- Momentum mais forte (follows VOL_EXP)
- Risco de transição para PANIC_PHASE se continuar expandindo

**Edges válidos:**
- MOM_CONT: alta validade (momentum real em curso)
- VOL_EXP: pode estar ativo (expansão em progresso)

**Postura do sistema:**
- MODO OPERACIONAL com monitoramento intensificado
- Verificar ATR a cada nova vela — próximo ao gatilho Northington
- Se ATR cruzar 1,5x: transição imediata para PANIC_PHASE

**Detecção:**
```
ATR_medio_20 × 1.00 < ATR_atual ≤ ATR_medio_20 × 1.50  →  EXPANSION_PHASE
```

---

### REG-VOL-04 — PANIC_PHASE

**Definição:**
ATR atual > 1,5x ATR médio das últimas 20 velas.
Filtro Northington ativo. Sistema entra em modo SENTINELA. Zero operações.

**Características:**
- Slippage imprevisível — pode ser 2x, 5x o nominal
- Spread bid-ask explode
- Fluxo é de liquidação, não direcional explorado por retail
- Regime de choque institucional

**Edges válidos:**
- NENHUM — sistema em standby completo

**Postura do sistema:**
- MODO SENTINELA: leitura e log apenas, nenhuma ordem
- Cancelar todas as ordens pendentes imediatamente
- Aguardar normalização: ATR_atual < ATR_medio_20 × 1,5 por pelo menos 3 velas consecutivas

**Detecção:**
```
ATR_atual > ATR_medio_20 × 1.50  →  PANIC_PHASE (Filtro Northington)
```

**Log obrigatório:**
```
[RISK] PANIC_PHASE | ATR={x:.2f} | Limite={y:.2f} | Sistema em modo SENTINELA
```

---

## DIMENSÃO 2 — DIRECIONALIDADE

Define a estratégia dentro do regime de volatilidade operável (REG-VOL-01 a 03).

---

### REG-DIR-01 — TREND_DAY

**Definição:**
Dia com tendência intraday clara e sustentada. Mercado forma sequência de máximas
e mínimas crescentes (alta) ou decrescentes (baixa) sem rotação significativa.

**Características:**
- Momentum se sustenta por múltiplas velas sem inversão
- Pullbacks são rasos (< 1x ATR)
- Volume consistente na direção da tendência
- Abertura na direção da tendência e manutenção até fechamento da Janela

**Edges válidos:**
- MOM_CONT: máxima validade — é o regime primário deste edge
- TIME_OPEN: amplifica MOM_CONT na abertura
- VOL_EXP: válido se precedido por compressão
- LIQ_SURGE: confirma MOM_CONT

**Edges reduzidos:**
- MOM_REVERSAL: baixa validade — reversões são pullbacks, não inversões
- MR_INTRA: baixa validade — extensões persistem em TREND_DAY (Clenow: "trend days run further")
- AUC_FAIL: baixa validade — falhas de leilão podem ser pullbacks apenas

**Identificação intraday:**
```
Velas 1-3 da Janela: direção consistente + volume acima da média  →  candidato TREND_DAY
Após vela 5: sem reversão ≥ 2x ATR  →  TREND_DAY confirmado
```

---

### REG-DIR-02 — ROTATION_DAY

**Definição:**
Dia sem tendência clara. Mercado oscila dentro de um range definido.
Alta e baixa são testadas alternadamente sem rompimento sustentado.

**Características:**
- Momentum não se sustenta além de 2-3 velas
- Reversões frequentes nos extremos do range
- Volume distribuído nas duas direções (sem lado dominante)
- MOM_CONT frequentemente falso (FM-SIG-01 elevado)

**Edges válidos:**
- MOM_REVERSAL: máxima validade — regime primário deste edge
- AUC_FAIL: alta validade — extremos do range são testados e rejeitados
- MR_INTRA: validade moderada — retornos à média são mais frequentes
- AUC_IMBAL: válido apenas na abertura antes de confirmar rotação

**Edges reduzidos:**
- MOM_CONT: baixa validade — FALSE_BREAKOUT frequente
- VOL_EXP: baixa validade — expansões não têm follow-through

**Identificação intraday:**
```
Após 3 sinais de MOM_CONT com reversão imediata  →  candidato ROTATION_DAY
Range da sessão consolidado por ≥ 5 velas  →  ROTATION_DAY confirmado
```

---

### REG-DIR-03 — OPENING_IMBALANCE_DAY

**Definição:**
Abertura com gap ou desequilíbrio claro que domina os primeiros 15-30 minutos.
Pode evoluir para TREND_DAY ou resolver o gap e virar ROTATION_DAY.

**Características:**
- Primeiros 15 minutos são dominados pelo AUC_IMBAL de abertura
- Direção inicial pode ser sustentada (→ TREND_DAY) ou revertida (→ ROTATION_DAY)
- Alta incerteza de classificação antes de 10:20

**Edges válidos:**
- TIME_OPEN: máxima validade — este é o regime primário deste edge
- AUC_IMBAL: alta validade
- MOM_CONT: válido apenas após confirmação de que imbalance é sustentado

**Postura do sistema:**
- Aguardar até 10:05 (SESSION_TRANSITION_BLOCK)
- Observar as primeiras 3-4 velas para classificação de regime
- Não comprometer capital antes de identificar se vai virar TREND ou ROTATION

---

## DIMENSÃO 3 — FASE TEMPORAL (Intraday)

Define o contexto dentro da Janela de Ouro.

---

### REG-TIME-01 — OPENING_PHASE

**Definição:** 10:00 – 10:30

**Características:**
- Maior volume da sessão
- Maior probabilidade de imbalance e momentum
- Maior risco de SLIPPAGE_EXPLOSION (10:00–10:05)
- SESSION_TRANSITION_BLOCK ativo até 10:05

**Postura:** Aguardar até 10:05, então avaliar com máxima atenção.

---

### REG-TIME-02 — CORE_PHASE

**Definição:** 10:30 – 11:30

**Características:**
- Volume estabilizado em nível operacional
- Parâmetros nominais do sistema em plena validade
- Melhor relação risco/retorno da sessão para execução retail
- Regime mais fácil de classificar (TREND vs. ROTATION já claro)

**Postura:** MODO OPERACIONAL pleno.

---

### REG-TIME-03 — DECAY_PHASE

**Definição:** 11:30 – 12:15

**Características:**
- Volume declinante
- Spread efetivo levemente maior
- FALSE_BREAKOUT mais frequente (TIME_DECAY ativo)
- Sinais de MOM_CONT requerem volume > 1,5x média (threshold elevado)

**Postura:** MODO OPERACIONAL com filtros reforçados.

---

### REG-TIME-04 — CLOSE_PHASE

**Definição:** 12:15 – 12:30

**Características:**
- Fluxo de fechamento — posições sendo encerradas
- Movimento contra a tendência do dia é frequente (liquidação)
- Qualquer sinal neste período tem baixa probabilidade de follow-through

**Postura:** BLOQUEAR novas entradas. Gerenciar posições abertas apenas.

---

## MATRIZ DE COMPATIBILIDADE REGIME × EDGE

| Edge | LOW_VOL | NORMAL_VOL | EXPANSION | PANIC | TREND_DAY | ROTATION_DAY |
|---|---|---|---|---|---|---|
| VOL_EXP | Preparar | ✔ | ✔ | ✘ | ✔ | Moderado |
| MOM_CONT | ✘ | ✔ | ✔ | ✘ | ✔✔ | ✘ |
| MOM_REVERSAL | ✘ | ✔ | Moderado | ✘ | ✘ | ✔✔ |
| AUC_IMBAL | ✘ | ✔ | ✔ | ✘ | ✔ | Moderado |
| AUC_FAIL | ✘ | ✔ | Moderado | ✘ | ✘ | ✔✔ |
| AUC_BREAK | Aguardar | ✔ | ✔ | ✘ | ✔ | ✘ |
| MR_INTRA | ✘ | ✔ | Moderado | ✘ | ✘ | ✔ |
| LIQ_VOID | BLOQUEIA | BLOQUEIA | BLOQUEIA | BLOQUEIA | BLOQUEIA | BLOQUEIA |
| VOL_SPIKE | — | — | — | SENTINELA | — | — |

Legenda: ✔✔ = regime primário | ✔ = válido | Moderado = filtros extras | ✘ = inválido | BLOQUEIA = bloqueio total

---

## TRANSIÇÕES DE REGIME

```
LOW_VOLATILITY
    │
    ├── ATR começa a crescer → NORMAL_VOLATILITY
    └── ATR continua caindo → VOL_COMP mais profundo

NORMAL_VOLATILITY
    │
    ├── ATR > 1.0x média → EXPANSION_PHASE
    └── ATR < 0.7x média → LOW_VOLATILITY

EXPANSION_PHASE
    │
    ├── ATR > 1.5x média → PANIC_PHASE (Northington bloqueia)
    └── ATR recua → NORMAL_VOLATILITY

PANIC_PHASE
    │
    └── ATR < 1.5x média por 3 velas consecutivas → NORMAL_VOLATILITY
        (nunca retornar diretamente para EXPANSION ou LOW)
```

---

## ALERTAS PARA VALIDAÇÃO DeepSeek R1

- [ ] REG-DIR-03 (OPENING_IMBALANCE_DAY): verificar se merece categoria própria ou é sub-caso de TREND_DAY
- [ ] Thresholds da Dimensão de Volatilidade (0.70x, 1.50x): validar contra dados históricos WDO
- [ ] ROTATION_DAY: definir critério quantitativo preciso de identificação (3 reversões? range < X pontos?)
- [ ] DECAY_PHASE: validar se 11:30 é o threshold correto para WDO ou se deve ser 11:00 ou 12:00
- [ ] Matriz de compatibilidade: verificar se AUC_IMBAL em ROTATION_DAY deve ser ✘ em vez de Moderado

---

*Arquivo gerado para validação externa. Classificação final: exclusividade DeepSeek R1 com DeepThink.*
