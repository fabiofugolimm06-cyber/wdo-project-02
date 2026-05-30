# EXECUTION_CONSTRAINTS.md
# WDO-EVOLVED-QUANT | /03_EDGE_TAXONOMY
# Versão: 1.0 | Status: AGUARDANDO VALIDAÇÃO DeepSeek R1

---

## DEFINIÇÃO OPERACIONAL DE EXECUTION CONSTRAINT

Execution constraint é uma **limitação real, não teórica, da infraestrutura retail**
que modifica, degrada ou impossibilita a exploração de um edge em condições reais.

Diferença crítica:
- **Edge**: existe no mercado
- **Execution constraint**: determina se o edge é **acessível** para esta infraestrutura

Um edge pode existir e ser inexplorado por esta plataforma por conta de constraints.
Neste caso, o edge é registrado mas marcado como INACCESSIBLE nesta infraestrutura.

---

## PERFIL DE INFRAESTRUTURA — WDO-EVOLVED-QUANT

```
Plataforma:     Profit One (Nelogica)
Linguagem:      NTSL (NeoTraderScript Language)
Execução:       via PostMessage/API Profit
Latência:       100–500ms (estimada, sem colocation)
Colocation:     NÃO
Co-location B3: NÃO
Feed de dados:  Profit One (dados B3 via distribuidor)
Ativo:          WDO (Mini Dólar futuro B3)
Tipo de ordem:  Mercado (padrão) | Limite (casos específicos)
```

---

## CONSTRAINTS DE LATÊNCIA

---

### EC-LAT-01 — MAX_SIGNAL_AGE

**Definição:**
Um sinal de entrada tem validade máxima de 1 vela Renko 8R após sua geração.
Após este prazo, o contexto que gerou o sinal não é mais válido.

**Valor:** 1 vela Renko 8R

**Fundamento:**
Com latência retail de 100–500ms e velas Renko 8R que podem se completar em
30–120 segundos em momentos de movimento, há risco real de que a vela seguinte
tenha começado antes da ordem ser executada.
Um sinal de MOM_CONT gerado na Vela 2 que só é executado na Vela 4 não é MOM_CONT —
é entrada no meio do movimento com risco/retorno degradado.

**Implementação:**
```python
MAX_LATENCIA_VELAS = 1

if velas_desde_sinal > MAX_LATENCIA_VELAS:
    logging.warning(
        f"[AUTOMATOR] Ordem cancelada: latência excedeu {MAX_LATENCIA_VELAS} vela(s) | "
        f"Sinal: vela {vela_sinal} | Atual: vela {vela_atual}"
    )
    cancelar_ordem()
```

**Ação:** CANCELAR — não executar com sinal vencido

---

### EC-LAT-02 — EXECUTION_WINDOW

**Definição:**
Para infraestrutura retail com latência 100–500ms, o tempo efetivo entre detecção
do sinal e confirmação de execução pode chegar a 1–2 segundos em pior caso.

**Implicação:**
Em velas Renko 8R de alta velocidade (movimentos de 8 pontos em < 10 segundos),
a ordem pode ser confirmada quando o preço já está 1–2 pontos além do ponto ideal.

**Mitigação:**
- Usar ordens a mercado para entradas (não limite) — aceitar slippage modelado
- Nunca tentar "melhorar o preço" com ordem limite em sinal de momentum
- O custo de ordem limite que não executa (perda de oportunidade) > custo de slippage

**Constraint permanente:** não eliminável sem colocation.

---

## CONSTRAINTS DE VOLATILIDADE

---

### EC-VOL-01 — ATR_REGIME_BLOCK

**Definição:**
Operações são bloqueadas quando ATR atual > 1,5x ATR médio das últimas 20 velas.

**Valor:** ATR_atual > ATR_medio_20 × 1,5

**Fundamento (Northington):**
Filtro de inatividade de Kirk Northington. Em regime de volatilidade anômala,
o slippage real é imprevisível e pode superar qualquer edge esperado.
O sistema entra em modo SENTINELA.

**Implementação:**
```python
def check_volatility_filter(self, atr_atual: float, atr_medio: float) -> bool:
    if atr_atual > (atr_medio * 1.5):
        logging.warning(
            f"[RISK] ATR_REGIME_BLOCK | ATR atual={atr_atual:.2f} | "
            f"Limite={atr_medio * 1.5:.2f} | Northington SENTINELA"
        )
        return False
    return True
```

**Prioridade:** ABSOLUTA — nenhum outro sinal pode sobrescrever este bloco

---

### EC-VOL-02 — HIGH_SPREAD_BLOCK

**Definição:**
Operações são bloqueadas quando o spread estimado excede o parâmetro de slippage nominal.

**Valor:** Spread_estimado > 0,5 ponto

**Fundamento:**
O position sizing assume custo de execução = 0,5 ponto (slippage B3 nominal).
Quando o spread real excede este valor, o modelo de custo está subestimando
o custo real e a fórmula de position sizing perde validade.

**Proxy de detecção** (quando dado de spread direto não disponível):
```python
# Proxy via condições de mercado:
spread_risk = (
    atr_atual > atr_medio_20 * 1.2 or      # volatilidade elevada
    volume_atual < volume_medio_20 * 0.4    # liquidez reduzida
)
if spread_risk:
    logging.warning("[RISK] HIGH_SPREAD_BLOCK | Spread estimado elevado | Operação bloqueada")
    return False
```

---

## CONSTRAINTS DE HORÁRIO

---

### EC-TIME-01 — SESSION_TRANSITION_BLOCK

**Definição:**
Entradas bloqueadas nos primeiros 5 minutos da Janela de Ouro (10:00–10:05).

**Valor:** Horário < 10:05

**Fundamento:**
Os primeiros minutos da sessão B3 concentram execução de ordens represadas overnight.
Volatilidade e slippage são imprevisíveis. Infraestrutura retail não consegue
competir com a velocidade de execução institucional neste período.

**Implementação:**
```python
def is_within_execution_window(self, hora_atual: str) -> bool:
    """
    Janela de Ouro: 10:00–12:30
    SESSION_TRANSITION_BLOCK: 10:00–10:05
    Execução real liberada: 10:05–12:15
    PRE_CLOSE_BLOCK: 12:15–12:30
    """
    return "10:05" <= hora_atual <= "12:15"
```

---

### EC-TIME-02 — GOLDEN_WINDOW_BLOCK

**Definição:**
Nenhuma operação é permitida fora da Janela de Ouro (antes de 10:00 ou após 12:30).

**Valor:** Horário < 10:00 ou Horário > 12:30

**Fundamento:**
A Janela de Ouro concentra a liquidez institucional relevante para WDO intraday.
Fora desta janela, o edge histórico não foi validado e a liquidez é insuficiente
para execução retail eficiente.

**Implementação:**
```python
def is_within_golden_window(self, hora_atual: str) -> bool:
    return "10:00" <= hora_atual <= "12:30"
```

**Prioridade:** ABSOLUTA — sistema fora desta janela = modo SENTINELA total

---

### EC-TIME-03 — PRE_CLOSE_BLOCK

**Definição:**
Novas entradas bloqueadas após 12:15. Apenas gestão de posições abertas permitida.

**Valor:** Horário > 12:15

**Fundamento:**
Fluxo de fechamento de posições domina os últimos 15 minutos.
Qualquer novo sinal neste período tem alta probabilidade de ser contra-fluxo —
gerado por fechamento de posições, não por novo desequilíbrio direcional.

---

## CONSTRAINTS DE CAPITAL E SIZING

---

### EC-SIZE-01 — POSITION_SIZING_FLOOR

**Definição:**
Número de contratos sempre calculado com math.floor() — nunca round() ou int() direto.
O piso matemático é lei: nunca arredondar para cima.

**Fórmula obrigatória:**
```python
import math

stop_real_pontos = atr_atual + 0.5           # slippage B3 incluído
custo_por_contrato = stop_real_pontos * 10.0 # R$10 por ponto WDO

n_contratos = math.floor(
    (capital * 0.01) / custo_por_contrato
)
```

**Fundamento (Vince):**
Ralph Vince: position sizing com arredondamento para cima viola a lei do piso
e expõe capital além do 1% definido. É uma violação matemática, não preferência.

**Erro proibido:**
```python
# PROIBIDO:
n_contratos = round(capital * 0.01 / custo_por_contrato)
n_contratos = int(capital * 0.01 / custo_por_contrato)
```

---

### EC-SIZE-02 — MINIMUM_CAPITAL_THRESHOLD

**Definição:**
Se math.floor() resultar em 0 contratos, operação é bloqueada.
O capital atual é insuficiente para operar 1 contrato dentro do risco de 1%.

**Implementação:**
```python
if n_contratos < 1:
    logging.info(
        f"[RISK] Capital insuficiente | ATR={atr_atual:.2f} | "
        f"Capital necessário para 1 contrato = R${custo_por_contrato / 0.01:.2f}"
    )
    return {"status": "BLOQUEADO", "motivo": "Capital insuficiente para 1 contrato"}
```

---

### EC-SIZE-03 — SLIPPAGE_INCLUSION_MANDATORY

**Definição:**
O slippage de 0,5 ponto deve estar incluído em TODOS os cálculos de custo de stop.
Nunca calcular stop sem incluir o pedágio B3.

**Valor fixo:** 0,5 ponto (R$ 5,00 por contrato)

**Implementação obrigatória:**
```python
SLIPPAGE_B3 = 0.5  # constante — nunca alterar sem auditoria

stop_real_pontos = atr_atual + SLIPPAGE_B3  # sempre
```

**Fundamento:**
O slippage de 0,5 ponto não é estimativa — é o custo estrutural de execução
em infraestrutura retail no WDO/B3. Omitir este valor cria modelo de custo
otimista que superestima o edge esperado.

---

## CONSTRAINTS DE SINAL

---

### EC-SIG-01 — VELA2_PHYSICAL_BREAKOUT

**Definição:**
Confirmação de sinal de MOM_CONT requer rompimento físico mínimo de 0,5 ponto
da máxima (compra) ou mínima (venda) da Vela 1.

**Valor:** ≥ 0,5 ponto além do extremo da Vela 1

**Implementação:**
```python
# Compra:
sinal_compra = close_vela2 > high_vela1 + 0.5

# Venda:
sinal_venda = close_vela2 < low_vela1 - 0.5
```

**Fundamento (Northington):**
Fechamento "da mesma cor" sem rompimento do extremo é exaustão disfarçada,
não momentum real. O rompimento físico de 0,5 ponto é o threshold mínimo
para separar noise de sinal com confiança.

---

### EC-SIG-02 — STOP_DYNAMIC_MANDATORY

**Definição:**
Stop loss é sempre dinâmico, recalculado a cada nova vela.
Stop fixo em pontos é proibido.

**Implementação:**
```python
# A cada nova vela:
stop_atual = calcular_atr_atual(velas[-20:]) + SLIPPAGE_B3

# PROIBIDO:
stop_fixo = 8  # nunca
```

**Fundamento:**
ATR do WDO varia significativamente durante a Janela de Ouro
(expansão NY após 10:30 aumenta ATR materialmente).
Stop fixo cria exposição assimétrica invisível: muito apertado quando ATR expande,
muito largo quando ATR contrai — o inverso do desejado.

---

## TABELA RESUMO — EXECUTION_CONSTRAINTS

| ID | Nome | Tipo | Valor | Prioridade | Contornável? |
|---|---|---|---|---|---|
| EC-LAT-01 | MAX_SIGNAL_AGE | Latência | 1 vela máx | ALTA | Não (infraestrutura) |
| EC-LAT-02 | EXECUTION_WINDOW | Latência | 100–500ms | ESTRUTURAL | Não sem colocation |
| EC-VOL-01 | ATR_REGIME_BLOCK | Volatilidade | ATR > 1,5x média | ABSOLUTA | Não |
| EC-VOL-02 | HIGH_SPREAD_BLOCK | Volatilidade | Spread > 0,5pt | ALTA | Não |
| EC-TIME-01 | SESSION_TRANSITION_BLOCK | Horário | < 10:05 | ALTA | Não |
| EC-TIME-02 | GOLDEN_WINDOW_BLOCK | Horário | < 10:00 ou > 12:30 | ABSOLUTA | Não |
| EC-TIME-03 | PRE_CLOSE_BLOCK | Horário | > 12:15 | ALTA | Não |
| EC-SIZE-01 | POSITION_SIZING_FLOOR | Sizing | math.floor() obrigatório | ABSOLUTA | Não |
| EC-SIZE-02 | MINIMUM_CAPITAL_THRESHOLD | Sizing | n_contratos ≥ 1 | ABSOLUTA | Não |
| EC-SIZE-03 | SLIPPAGE_INCLUSION_MANDATORY | Sizing | +0,5pt em todo stop | ABSOLUTA | Não |
| EC-SIG-01 | VELA2_PHYSICAL_BREAKOUT | Sinal | ≥ 0,5pt rompimento | ALTA | Não |
| EC-SIG-02 | STOP_DYNAMIC_MANDATORY | Sinal | ATR dinâmico | ABSOLUTA | Não |

---

## HIERARQUIA DE PRIORIDADE

```
ABSOLUTA (violação = falha de sistema, nunca sobrescrita por sinal):
  EC-VOL-01  ATR_REGIME_BLOCK
  EC-TIME-02 GOLDEN_WINDOW_BLOCK
  EC-SIZE-01 POSITION_SIZING_FLOOR
  EC-SIZE-02 MINIMUM_CAPITAL_THRESHOLD
  EC-SIZE-03 SLIPPAGE_INCLUSION_MANDATORY
  EC-SIG-02  STOP_DYNAMIC_MANDATORY

ALTA (bloqueia operação mas pode ser revisada em versão futura):
  EC-LAT-01  MAX_SIGNAL_AGE
  EC-VOL-02  HIGH_SPREAD_BLOCK
  EC-TIME-01 SESSION_TRANSITION_BLOCK
  EC-TIME-03 PRE_CLOSE_BLOCK
  EC-SIG-01  VELA2_PHYSICAL_BREAKOUT

ESTRUTURAL (limitação permanente da infraestrutura — documentar, não resolver):
  EC-LAT-02  EXECUTION_WINDOW
```

---

## ALERTAS PARA VALIDAÇÃO DeepSeek R1

- [ ] EC-TIME-01: validar threshold 10:05 vs. 10:00 — literatura sugere variação (alguns autores: 10:00, outros: 10:10)
- [ ] EC-TIME-03: validar threshold 12:15 vs. 12:30 — diferença de 15 min de operação
- [ ] EC-VOL-02: o proxy de HIGH_SPREAD_BLOCK é suficiente ou é necessário dado real de spread?
- [ ] EC-SIG-01: 0,5 ponto é threshold correto para WDO Renko 8R ou deve ser calibrado para ATR/box size?
- [ ] EC-LAT-01: 1 vela é o threshold correto ou deve ser 2 velas dado latência estrutural de 100–500ms?

---

*Arquivo gerado para validação externa. Classificação final: exclusividade DeepSeek R1 com DeepThink.*
