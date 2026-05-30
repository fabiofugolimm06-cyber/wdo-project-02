PROJETO WDO‑EVOLVED‑QUANT - ESTADO ATUAL (data: 26/05/2026)

Objetivo: Construir robô quantitativo para WDO (Mini Dólar B3) com validação institucional.

Pipeline de dados: Funcional – lê CSV com separador ; e decimal ,, gera arquivos processados.

Módulos de validação: Todos implementados em 07_VALIDATION/ (walk_forward, custos, regime, métricas, Monte Carlo, etc.)

Resultados (out‑of‑sample com custos reais):
- Nenhuma estratégia simples (Donchian, Bollinger, volume, regime) teve expectancy líquida positiva.
- Melhor: Donchian+volume em 5min → –0,88 pontos por trade, win rate 44,4%.
- Sinal de volume extremo teve expectancy +0,049% mas não significativo.

Conclusão: Estratégias lineares simples não funcionam no WDO 1min com custos reais.

Próximos passos possíveis:
- Testar WIN (mini-índice)
- Mudar para timeframe 15min (agregar dados WDO existentes)
- Avançar para microestrutura (dados de tick)
- Encerrar e documentar o framework

Decisão tomada: Testar timeframe 15min primeiro.