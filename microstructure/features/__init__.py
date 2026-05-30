"""
microstructure.features
-----------------------
Feature registry and BaseFeature hierarchy.

Usage
-----
    from microstructure.features.registry import autodiscover, REGISTRY
    autodiscover()            # imports all feature modules, triggers @register_feature
    REGISTRY.list()           # ['delta', ...]
    feat = REGISTRY.get('delta')()
"""
