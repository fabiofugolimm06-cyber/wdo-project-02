# RELATÓRIO DE IMPLEMENTABILIDADE – NTSL (Profit One)

## ET-01 compressionBreakout
- **Observabilidade**: total (ATR, preço, volume)
- **Dependência institucional**: nenhuma
- **Implementabilidade**: IMPLEMENTABLE

## ET-02 momentumPersistence
- **Observabilidade**: total (sequência de velas, rompimento físico, volume)
- **Dependência institucional**: nenhuma
- **Implementabilidade**: IMPLEMENTABLE

## ET-03 reversionTrap
- **Observabilidade**: total (VWAP, ATR, preço)
- **Dependência institucional**: VWAP pode ser computado localmente
- **Implementabilidade**: IMPLEMENTABLE

## ET-04 auctionImbalance
- **Observabilidade**: proxy via direção de candle (up volume = volume em alta, down volume = volume em baixa)
- **Dependência institucional**: sem L2 ou tape real, o proxy é grosseiro
- **Implementabilidade**: PARTIALLY_IMPLEMENTABLE (use com cautela)

## ET-05 auctionFailure
- **Observabilidade**: total (preço, níveis de suporte/resistência)
- **Dependência institucional**: níveis precisam ser definidos (ex: máximas/mínimas recentes)
- **Implementabilidade**: IMPLEMENTABLE

## Resumo
- **IMPLEMENTABLE**: ET-01, ET-02, ET-03, ET-05
- **PARTIALLY_IMPLEMENTABLE**: ET-04
- **NOT_IMPLEMENTABLE**: nenhum (após remoção de ET-LIQ-01, etc.)
