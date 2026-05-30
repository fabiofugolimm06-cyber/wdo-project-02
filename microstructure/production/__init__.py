"""
microstructure/production — saída padronizada para produção (v1).
"""

from microstructure.production.production_bridge_v1 import (
    build_production_packet,
    build_production_packets_ordered,
    packets_to_ntsl_bundle,
    validate_production_packet,
)
from microstructure.production.production_spec_v1 import ProductionSpecV1

__all__ = [
    "ProductionSpecV1",
    "build_production_packet",
    "build_production_packets_ordered",
    "validate_production_packet",
    "packets_to_ntsl_bundle",
]
