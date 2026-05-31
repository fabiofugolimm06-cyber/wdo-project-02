"""System Simplification Layer — mapa de deps, superfície, complexidade e redundância."""

from src.simplification.complexity_reducer import ComplexityReducer
from src.simplification.dependency_map import DependencyMap, LAYER_ORDER
from src.simplification.gate_overlap_detector import GateOverlapDetector
from src.simplification.layer_merger import LayerMerger
from src.simplification.redundancy_analyzer import RedundancyAnalyzer
from src.simplification.system_surface import SystemSurface

__all__ = [
    "ComplexityReducer",
    "DependencyMap",
    "GateOverlapDetector",
    "LAYER_ORDER",
    "LayerMerger",
    "RedundancyAnalyzer",
    "SystemSurface",
]
