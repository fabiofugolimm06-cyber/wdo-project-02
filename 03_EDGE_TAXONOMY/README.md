# WDO-EVOLVED-QUANT | /03_EDGE_TAXONOMY

## Arquitetura final (pós-auditoria)

Esta pasta contém a base canônica do sistema de edges, pronta para canonicalização e implementação.

### Estrutura

- EDGE_TYPES.yaml: 5 tipos ortogonais de edge (ET-01 a ET-05)
- MARKET_REGIMES.yaml: regimes de mercado (volatilidade, direcionalidade, fase)
- EXECUTION_CONSTRAINTS.yaml: limitações absolutas da infraestrutura retail
- FAILURE_MODES.yaml: modos de falha por categoria
- SIGNAL_ONTOLOGY/: triggers, confirmações e invalidações
- MATRIZ_ORTOGONALIDADE.md: prova formal de ortogonalidade
- IMPLEMENTABILITY_REPORT.md: classificação de implementabilidade no NTSL

### Princípios

- Edge = assimetria estatística mensurável
- Regime = estado estrutural do mercado (não edge)
- Constraints = absolutas e inegociáveis
- Invalidação > Confirmação (precedência)

### Próximos passos

1. Calibrar thresholds com dados tick-level WDO
2. Canonicalizar edges
3. Implementar no NTSL (Profit One)
