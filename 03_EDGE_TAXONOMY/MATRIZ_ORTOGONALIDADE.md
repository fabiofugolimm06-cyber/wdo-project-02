# MATRIZ FORMAL DE ORTOGONALIDADE ENTRE ET-01 → ET-05

## Definição de ortogonalidade semântica
Dois edges são ortogonais se:
- mecanismos causais são distintos
- não podem ser simultaneamente verdadeiros com mesmo trigger
- observáveis não são redutíveis entre si

## Matriz de comparação

| Edge | Mecanismo causal | Observáveis primários | Trigger típico | Regime principal |
|------|------------------|----------------------|----------------|------------------|
| ET-01 | Acumulação latente em compressão | ATR, rompimento físico, volume | Preço rompe nível após ATR baixo | LOW_VOL → NORMAL_VOL |
| ET-02 | Inércia posicional | Sequência de velas, rompimento físico, volume | Vela2 > high_v1 + 0.5 | TREND_DAY |
| ET-03 | Exaustão + atração valor justo | Desvio de VWAP/ATR, vela de rejeição | Preço > VWAP + 2x ATR | ROTATION_DAY |
| ET-04 | Assimetria de fluxo | Volume up/down em janela | (volume_up - volume_down) / total > 0.6 | OPENING_PHASE |
| ET-05 | Falha de aceitação | Toque em nível, fechamento dentro do range | Preço toca suporte/resistência pela 2ª vez | ROTATION_DAY |

## Prova de não sobreposição

- ET-01 exige compressão prévia (ATR baixo). Nenhum outro edge exige isso.
- ET-02 exige duas velas consecutivas na mesma direção com rompimento ≥0.5pt. ET-03 e ET-05 exigem reversão.
- ET-03 exige desvio do VWAP > 2x ATR. ET-02 e ET-04 podem ocorrer sem desvio.
- ET-04 exige janela de tempo e dados de fluxo. ET-01, ET-02, ET-03, ET-05 não usam fluxo.
- ET-05 exige toque em nível estrutural e fechamento dentro do range. ET-02 e ET-03 não consideram níveis fixos.

Portanto, são ortogonais.
