📊 RELATÓRIO COMPLETO DO PROJETO WDO‑EVOLVED‑QUANT
Fase 1: Validação de Estratégias Lineares Clássicas no Mini Dólar (WDO)
Data de conclusão: 27/05/2026
Status: ✅ FASE 1 CONCLUÍDA (resultado negativo, mas cientificamente válido)
Próximo ambiente: Cursor + Claude Code (Fase 2 - Market Structure)

ÍNDICE
Visão Geral do Projeto

O que DEU CERTO (entregues com sucesso)

O que DEU ERRADO (falhas e obstáculos)

O que FOI TENTADO (lista exaustiva)

Resultados Consolidados (todos os testes)

Validação Estatística Rigorosa

Arquitetura do Framework Entregue

Problemas Técnicos Enfrentados e Soluções

O que NÃO FOI TENTADO (limitações da Fase 1)

O que PRECISA SER AJUSTADO para evoluir

Próximos Passos (Fase 2 - Market Structure)

Conclusão Científica

1. VISÃO GERAL DO PROJETO
Objetivo Original
Construir um robô quantitativo para o contrato WDO (Mini Dólar B3) com validação institucional rigorosa, incluindo walk‑forward, custos reais e proteção contra overfitting.

Escopo da Fase 1
Testar estratégias lineares clássicas (Donchian, Bollinger, volume, regime switching) em múltiplos timeframes (1min, 5min, 15min) para determinar se existe edge explorável no WDO.

Resultado Final
✅ Framework construído e validado
❌ Nenhuma estratégia linear teve expectancy positiva após custos
✅ Conclusão estatística robusta: o desempenho observado é RUÍDO

2. O QUE DEU CERTO (entregues com sucesso)
2.1 Pipeline de Dados (100% funcional)
Componente	Descrição	Arquivo gerado
Leitura de CSV	Suporta separador ; e decimal ,	-
Parsing de datetime	Converte Date + Time ou campo único	-
Agregação temporal	1min → 5min, 15min, etc.	WDOFUT_OHLC.csv
Processamento final	Dados limpos e tipados	WDOFUT_processado.parquet
Exemplo de leitura bem-sucedida:

python
# Leitura de dados brutos (102.069 registros de 1min)
df = pd.read_csv(INPUT_CSV, sep=';', decimal=',')
df['datetime'] = pd.to_datetime(df['Date'] + ' ' + df['Time'])
2.2 Módulos de Validação (institucionais)
Módulo	Arquivo	Função	Status
Walk‑forward	walk_forward.py	Validação out‑of‑sample com janelas deslizantes	✅
Modelo de custos	cost_model.py	Slippage (0.5 pt) + corretagem (R$0.30)	✅
Filtro de regime	regime_filter.py	Volatilidade, horário, tendência	✅
Métricas avançadas	metrics_engine.py	Expectancy, Sharpe, drawdown, win rate	✅
Monte Carlo	monte_carlo.py	Bootstrap de trades (10.000 simulações)	✅
Estratégias	strategies.py	Donchian, Bollinger, volume, regime	✅
Comparação custos	compare_with_costs.py	Bruto vs líquido	✅
Eventos extremos	extreme_event_analysis.py	Event study pós‑volume extremo	✅
2.3 Estratégias Implementadas
python
# Todas as estratégias testadas
strategies = {
    'Donchian': donchian_signal,           # Breakout de máximas/mínimas
    'Bollinger': bollinger_signal,         # Reversão nas bandas
    'Donchian+Volume': donchian_volume_signal,  # Breakout com confirmação
    'Regime (baixa vol)': regime_vol_signal,    # Donchian + baixa volatilidade
    'ExtremeVolume': extreme_volume_signal      # Volume > 10x média
}
2.4 Framework Reutilizável
O código agora pode ser aplicado a qualquer outro ativo (WIN, ações, cripto, forex) com:

Mínimas alterações de configuração (caminho do CSV, nomes das colunas)

Mesma validação institucional

Custos ajustáveis por ativo

2.5 Documentação de Código
Todos os scripts principais possuem:

Docstrings explicativos

Configurações centralizadas no topo

Tratamento de erros

Logging de progresso

3. O QUE DEU ERRADO (falhas e obstáculos)
3.1 Estratégias (falha central)
Estratégia	Resultado	Causa provável
Donchian puro	Expectancy negativa (-0.62 pts)	Ruído + custos
Donchian+Volume	Expectancy negativa (-0.88 pts)	Volume não filtra corretamente
Bollinger	Expectancy negativa	Mercado não reverter ao extremo
Regime switching	Expectancy negativa	Regime não persiste o suficiente
Volume extremo	Expectancy bruta +0.049% (não significativa)	Bootstrap rejeita significância
Conclusão: Nenhuma estratégia linear explorou edge real no WDO.

3.2 Problemas Técnicos Encontrados
Problema	Como foi resolvido
Separação ; e decimal ,	Parâmetros SEP e DECIMAL configurados
Colunas em português (abertura, maxima, etc.)	Renomeação dinâmica no script
Colunas Date + Time separadas	Combinação com pd.to_datetime
Erro Invalid frequency: 15T	Substituído por 15min no resample
Erro No numeric types to aggregate	Conversão forçada com str.replace(',', '.').astype(float)
Arquivo trades_15min.csv não gerado	Correção do script para salvar trades
Módulo scipy não instalado	pip install scipy
3.3 Validação Estatística (falhou)
Todos os 4 testes estatísticos falharam em rejeitar H0 (média = 0):

Teste	Resultado	Significativo?
Bootstrap IC 95%	Contém zero	❌
Teste t (p-valor)	p > 0.05	❌
Permutation test	p > 0.05	❌
Estabilidade entre folds	Sinais opostos	❌
O dado mais revelador:

Fold 1: +12.89 pts por trade

Fold 2: -10.35 pts por trade

Fold 3: -2.66 pts por trade

Interpretação: Mesma estratégia, mesmos parâmetros → resultados opostos em diferentes períodos. Isso é a definição de ruído.

3.4 Tentativas Falhas
❌ Grid search paramétrico (não executado propositalmente - evitar overfitting)

❌ Otimização de lookbacks (testado 10, 20, 30, 50 - todos negativos)

❌ Filtros de volume (1.5x, 2x, 3x, 5x, 10x - pioraram ou zeraram trades)

❌ Timeframes maiores (15min continuou negativo)

❌ Filtros de regime (baixa volatilidade não melhorou)

4. O QUE FOI TENTADO (lista exaustiva)
4.1 Timeframes
Timeframe	Dados	Estratégias testadas	Resultado
1 minuto	Original (102k registros)	Donchian, Bollinger, volume	Negativo
5 minutos	Agregado do 1min	Donchian+Volume	Negativo (-0.96 pts)
15 minutos	Agregado do 1min	Donchian puro	Negativo (-0.62 pts)
4.2 Parâmetros das Estratégias
Estratégia	Parâmetros testados	Melhor resultado
Donchian	Lookback: 10, 20, 30, 50	20 (menos pior)
Bollinger	Window: 20, STD: 1.5, 2.0, 2.5	20/2.0 (menos pior)
Volume threshold	1.5x, 2x, 3x, 5x, 10x	1.5x (menos pior)
Regime vol	Threshold: 0.5x, 0.8x, 1.0x	0.8x (menos pior)
4.3 Filtros e Modificações
Filtro	Descrição	Resultado
Volume confirmação	Donchian + volume > média	Piorou (menos trades)
Regime baixa vol	Opera só quando vol < média	Piorou
Regime horário	Abertura (9-10h), meio (11-14h), fechamento (16-18h)	Todos negativos
Stop-loss fixo	3 pontos (não implementado em produção)	Não testado
4.4 Validações Realizadas
Método	Descrição	Status
Walk‑forward	Treino 3 meses, teste 1 mês	✅
Custos reais	Slippage 0.5 pt + R$0.30	✅
Bootstrap	10.000 simulações	✅
Teste t	Média vs zero	✅
Permutation test	Embaralhamento de sinais	✅
Estabilidade entre folds	Consistência temporal	✅
Comparação com aleatório	Entradas aleatórias	✅ (parcial)
5. RESULTADOS CONSOLIDADOS (todos os testes)
5.1 Tabela Principal
Timeframe	Estratégia	Expectancy líquida	Win rate	Trades	Sharpe (aprox)
1min	Donchian+Volume	-0.88 pts	44.4%	~200	Negativo
5min	Donchian+Volume	-0.96 pts	43.6%	204	Negativo
15min	Donchian puro	-0.62 pts	34.6%	52	Negativo
15min	Bollinger	Negativa	<40%	~30	Negativo
15min	Regime switching	Negativa	<35%	~20	Negativo
Todos	Extreme volume (10x)	+0.049%*	71.4%	42	*não significativo
*Bootstrap IC 95%: [-0.01%, +0.10%] → contém zero

5.2 Análise por Fold (Donchian 15min)
Fold	Período	Trades	Expectancy bruta
1	[início]	17	+12.89 pts
2	[meio]	17	-10.35 pts
3	[final]	18	-2.66 pts
Interpretação: A instabilidade entre folds (sinais opostos) é a evidência mais forte de que não há edge consistente.

5.3 Análise de Assimetria (Donchian 15min)
Métrica	Valor
Winners (25 trades)	Média: +0.81 pts
Losers (27 trades)	Média: -1.03 pts
Razão perda/ganho	1.27 (proporcional)
Pior trade	-2.10 pts
Melhor trade	+1.60 pts
Conclusão: Perdas e ganhos são proporcionais. O problema NÃO é cauda esquerda (perdas explosivas), mas sim win rate baixo + custos.

6. VALIDAÇÃO ESTATÍSTICA RIGOROSA
6.1 Metodologia
Implementamos um módulo completo de validação estatística (validacao_estatistica.py) com:

python
1. Bootstrap Confidence Interval (10.000 amostras)
2. Teste t de Student (média vs zero)
3. Permutation Test (embaralhamento de sinais)
4. Random Entry Comparison (entradas aleatórias)
5. Stability Across Folds (consistência temporal)
6.2 Resultados dos Testes
Teste	Estatística	p-valor	IC 95%	Significativo?
Bootstrap	Média obs: -0.62	-	[-1.20, +0.15]	❌ (contém zero)
Teste t	t = -0.84	0.405	-	❌ (p > 0.05)
Permutation	Média obs: -0.62	0.382	-	❌ (p > 0.05)
Random entries	Estratégia vs aleatório	0.330	-	❌ (não melhor)
Estabilidade	Folds com sinais opostos	-	-	❌ (inconsistente)
6.3 Conclusão Estatística
text
Criterios atendidos: 0/4

CONCLUSAO: A expectativa bruta NAO e estatisticamente diferente de zero.
O desempenho observado e consistente com RUIDO.
7. ARQUITETURA DO FRAMEWORK ENTREGUE
7.1 Estrutura de Pastas
text
WDO PROJECT 02/
│
├── 07_VALIDATION/                    # Módulos de validação (Fase 1)
│   ├── walk_forward.py               # Walk-forward validator
│   ├── cost_model.py                 # Modelo de custos
│   ├── regime_filter.py              # Filtros de regime
│   ├── metrics_engine.py             # Métricas avançadas
│   ├── monte_carlo.py                # Bootstrap e simulações
│   ├── strategies.py                 # Implementação das estratégias
│   ├── compare_with_costs.py         # Comparação bruto vs líquido
│   └── extreme_event_analysis.py     # Event study
│
├── 08_TESTES_15MIN/                  # Testes específicos 15min
│   ├── wdo_15min_donchian_puro.py    # Donchian puro em 15min
│   ├── wdo_15min_correcao.py         # Versão corrigida
│   ├── validacao_estatistica.py      # Validação estatística
│   ├── diagnostico_assimetria.py     # Análise de assimetria
│   ├── bootstrap_distribution.png    # Gráfico bootstrap
│   └── trades_15min.csv              # Trades gerados (52 registros)
│
├── data/
│   ├── raw/                          # Dados brutos (NÃO SUBIR PARA GIT)
│   │   ├── WDOFUT_OHLC.csv           # Seu arquivo original
│   │   └── WDOFUT_F_0_1min.csv       # Alternativa
│   └── processed/                    # Dados processados
│       ├── WDOFUT_processado.parquet
│       └── WDOFUT_OHLC.csv
│
└── graficos/                         # Gráficos gerados
    ├── expectancy_heatmap.png
    ├── extreme_event_study.png
    └── trades_wdo_5min.csv
7.2 Dependências Necessárias
python
# requirements.txt
pandas>=2.0.0
numpy>=1.24.0
scipy>=1.10.0
matplotlib>=3.7.0
7.3 Configurações Padrão
python
# Custos (Mini Dólar)
SLIPPAGE_POINTS = 0.5
COMMISSION_BRL = 0.30
POINT_VALUE = 10.0  # 1 ponto = R$10

# Walk-forward
TRAIN_BARS = 1800   # ~3 meses em 15min
TEST_BARS = 600     # ~1 mês

# Estratégias
DONCHIAN_LOOKBACK = 20
BOLLINGER_WINDOW = 20
BOLLINGER_STD = 2.0
VOLUME_THRESHOLD = 1.5
8. PROBLEMAS TÉCNICOS ENFRENTADOS E SOLUÇÕES
8.1 Problemas com Leitura de Dados
Problema	Solução	Código
Separador ;	sep=';'	pd.read_csv(..., sep=';')
Decimal ,	decimal=','	pd.read_csv(..., decimal=',')
Datetime em duas colunas	Combinar Date + Time	pd.to_datetime(df['Date'] + ' ' + df['Time'])
Colunas em português	Renomear dinamicamente	df.rename(columns={'abertura': 'open'})
Dados como string	Substituir , por .	str.replace(',', '.').astype(float)
8.2 Problemas com Agregação
Problema	Solução
Invalid frequency: 15T	Usar '15min' em vez de '15T'
No numeric types to aggregate	Converter tipos antes do resample
Perda de dados na agregação	Usar .dropna() após resample
8.3 Problemas com Trades
Problema	Solução
Nenhum trade gerado	Reduzir threshold de volume ou usar Donchian puro
Arquivo CSV não salvo	Adicionar trades_df.to_csv() no script
Trades duplicados	Resetar posição após cada saída
8.4 Problemas com Bibliotecas
Problema	Solução
ModuleNotFoundError: scipy	pip install scipy
ModuleNotFoundError: matplotlib	pip install matplotlib
9. O QUE NÃO FOI TENTADO (limitações da Fase 1)
9.1 Estratégias Não Testadas
Categoria	Estratégias	Razão para não testar
Machine Learning	Random Forest, XGBoost, LSTM	Foge do escopo da Fase 1 (lineares)
Microestrutura	Order flow, delta de volume	Exige dados de tick (não disponíveis)
Timeframes inferiores	15s, 30s, 1 tick	Exige dados de tick
Arbitragem estatística	Pairs trading, cointegração	Fora do escopo (WDO sozinho)
Opções	Volatilidade implícita, Greeks	Fora do escopo
9.2 Otimizações Não Realizadas (por princípio)
Técnica	Razão para não usar
Grid search extensivo	Evitar overfitting
Otimização Bayesiana	Evitar overfitting
Backtest com parâmetros fixos	Usamos walk-forward
Data snooping	Evitado propositalmente
Curva de equity sem custos	Custos inclusos desde o início
9.3 Dados Não Obtidos
Dados	Status	Impacto
Dados de tick do WDO	❌ Não obtidos	Impede microestrutura
Dados do WIN (mini-índice)	❌ Não obtidos	Impede teste em outro ativo
Dados de book de ofertas	❌ Não obtidos	Impede análise de liquidez
10. O QUE PRECISA SER AJUSTADO PARA EVOLUIR
10.1 Para Testar WIN (Mini-Índice)
Ajuste necessário	Descrição	Prioridade
Obter dados históricos	Baixar 1min do WIN (ex: Yahoo Finance, TrueData, MT5)	Alta
Ajustar ponto value	WIN: 1 ponto = R$0.20 (diferente do WDO)	Alta
Ajustar custos	Slippage pode ser diferente (mais líquido)	Média
Validar horários	WIN tem horário contínuo diferente	Baixa
Script para baixar dados do WIN (exemplo):

python
import yfinance as yf
win = yf.download("WIN=F", period="2y", interval="1m")
10.2 Para Avançar para Microestrutura
Ajuste necessário	Descrição	Complexidade
Obter dados de tick	Contratar fonte (ex: Bloomberg, TrueData, MT5)	Alta
Processar ordem flow	Identificar compras/vendas agressivas	Alta
Calcular delta de volume	Soma líquida de ordens agressivas	Média
Absorção de liquidez	Detectar grandes ordens passivas	Alta
Tape reading quantificado	Padrões de sequência de trades	Média
10.3 Para Testar Machine Learning
Ajuste necessário	Descrição	Complexidade
Criar features	Indicadores defasados, interações, transformações	Média
Separar treino/validação/teste	Múltiplos períodos	Média
Validar com walk-forward	Modelos retreinados periodicamente	Alta
Evitar overfitting	Regularização, early stopping, validação cruzada	Alta
Features sugeridas:

python
features = [
    'ret_lag_1', 'ret_lag_5', 'ret_lag_10',    # retornos defasados
    'vol_lag_1', 'vol_lag_5',                   # volatilidade
    'rsi_14', 'macd_diff',                      # indicadores clássicos
    'volume_ratio', 'volume_trend',             # volume
    'hour_sin', 'hour_cos', 'dow_sin', 'dow_cos' # sazonalidade
]
10.4 Para Melhorar o Framework Atual
Ajuste	Descrição	Esforço
Paralelização	Rodar walk-forward em múltiplos núcleos	Médio
Persistência de resultados	Salvar em banco de dados (SQLite)	Baixo
Dashboard web	Streamlit/Dash para visualização	Médio
Conexão com broker	Execução real (MetaTrader, B3 Direct)	Alto
Logging estruturado	Em vez de prints	Baixo
11. PRÓXIMOS PASSOS (FASE 2 - MARKET STRUCTURE)
11.1 Direção Recomendada
Com base nos resultados negativos para estratégias lineares, a recomendação é mudar de paradigma:

Paradigma atual	Novo paradigma
Estratégias lineares	Microestrutura
OHLC (preços)	Tick / ordem flow
Breakouts e reversões	Delta volume, absorção de liquidez
Regimes de volatilidade	Assimetria estrutural
11.2 Roteiro Sugerido para Fase 2
Etapa 1: Obter dados de tick (2-4 semanas)

Contratar fonte (TrueData, Bloomberg, ou API da B3)

Formato esperado: timestamp, price, volume, trade direction (buy/sell)

Etapa 2: Implementar análise de microestrutura (4-6 semanas)

python
# Exemplo de delta volume
def compute_delta_volume(trades):
    """
    trades: DataFrame com 'price', 'volume', 'side' ('B' ou 'S')
    """
    trades['delta'] = trades['volume'] * (1 if trades['side'] == 'B' else -1)
    delta_cum = trades['delta'].cumsum()
    return delta_cum
Etapa 3: Validar novas hipóteses (2-4 semanas)

Hipótese: absorção de liquidez precede reversão

Hipótese: delta extremo precede continuação

Hipótese: desequilíbrio de ordens agressivas gera edge

Etapa 4: Construir modelo não-linear (4-8 semanas)

Random Forest com features de microestrutura

Validar com walk-forward rigoroso

Comparar com baseline de ruído

11.3 Ou: Aplicar Framework a Outro Ativo (WIN)
Se a microestrutura for inviável, a alternativa mais promissora é:

Baixar dados do WIN (mini-índice B3)

Executar o mesmo framework (pipeline + validação + custos)

Comparar resultados com WDO (índice pode ter edge diferente)

python
# Script rápido para baixar WIN (após instalar yfinance)
import yfinance as yf
win = yf.download("WIN=F", start="2020-01-01", interval="1m")
win.to_csv("WIN_1min.csv")
12. CONCLUSÃO CIENTÍFICA
12.1 Resumo Executivo
O WDO (Mini Dólar B3) NÃO apresenta edge explorável por estratégias lineares clássicas (breakout, reversão, volume, regime switching) após custos reais de transação (slippage 0.5 ponto + R$0,30 corretagem).

O desempenho observado é estatisticamente indistinguível de ruído, conforme demonstrado por bootstrap, teste t, permutation test e análise de estabilidade entre folds.

12.2 Evidências Que Sustentam a Conclusão
Evidência	Força
Expectancy negativa em 1min, 5min e 15min	Forte
Bootstrap IC 95% contém zero	Muito forte
p-valor do teste t > 0.05	Muito forte
Permutation test não significativo	Muito forte
Folds com sinais opostos (+12.9 e -10.3)	Extremamente forte
Eventos extremos não significativos no bootstrap	Forte
12.3 O Que o Framework Permite Agora
✅ Testar qualquer outro ativo (WIN, ações, cripto, forex)
✅ Modificar custos (slippage, comissão, valor do ponto)
✅ Adicionar novas estratégias lineares
✅ Validar com walk-forward e Monte Carlo
✅ Gerar relatórios de significância estatística

12.4 O Que o Framework NÃO Permite (sem modificações)
❌ Microestrutura (dados de tick)
❌ Machine learning não-linear
❌ Timeframes inferiores a 1 minuto
❌ Execução real (integração com broker)

13. ARQUIVO MD PARA O CURSOR
Instruções para usar este relatório no Cursor:
Salve este relatório como RELATORIO_COMPLETO_WDO_EVOLVED_QUANT.md

Abra o Cursor e inicie um novo projeto

Cole o seguinte prompt inicial:

markdown
# PROMPT PARA O CURSOR (FASE 2)

Este é o relatório completo do projeto WDO-EVOLVED-QUANT, Fase 1 concluída.

## Resumo para o Cursor:

- **Objetivo da Fase 1:** Testar estratégias lineares clássicas no WDO (Mini Dólar B3)
- **Resultado:** Nenhuma estratégia teve expectancy positiva após custos reais
- **Validação estatística:** Média dos retornos brutos NÃO é diferente de zero (p > 0.05, bootstrap contém zero)
- **Conclusão:** O desempenho observado é consistente com ruído amostral

## O que foi entregue:

- Pipeline de dados funcional (CSV → parquet, agregação temporal)
- Módulos de validação (walk-forward, custos, regime, métricas, Monte Carlo, event study)
- Framework reutilizável para qualquer ativo OHLC

## O que NÃO foi testado (e precisa ser na Fase 2):

1. Microestrutura (dados de tick) → mais promissor para WDO
2. Machine learning não-linear (Random Forest, XGBoost)
3. Timeframes inferiores a 1 minuto
4. WIN (mini-índice) como ativo alternativo

## Decisão para Fase 2:

**Vamos avançar para MICROESTRUTURA** com foco em:
- Delta de volume (ordem flow)
- Absorção de liquidez
- Assimetria estrutural de caudas

## O que o Cursor precisa fazer agora:

1. Entender que não há edge em estratégias lineares (não perder tempo otimizando)
2. Sugerir como obter dados de tick do WDO (fontes, custos, formato)
3. Propor arquitetura para análise de microestrutura
4. Implementar protótipo de delta volume se os dados estiverem disponíveis

## Arquivos importantes para referência:

- `08_TESTES_15MIN/validacao_estatistica.py` → validação estatística
- `07_VALIDATION/` → módulos de validação reutilizáveis
- `trades_15min.csv` → 52 trades do Donchian 15min

**Aguardando orientação do Cursor para iniciar a Fase 2.**
14. ASSINATURA DO PROJETO
Projeto: WDO‑EVOLVED‑QUANT
Fase: 1 (Concluída)
Data: 27/05/2026
Status: ✅ Framework validado / ❌ Estratégias lineares ineficazes
Próxima fase: Market Structure Research (microestrutura)
Ambiente recomendado: Cursor + Claude Code