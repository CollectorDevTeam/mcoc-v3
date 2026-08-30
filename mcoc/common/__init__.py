# mcoc/common/__init__.py
"""
Minimal package init. Prefer explicit imports from submodules.
"""
from feature_system import CDTEntitlements
from .helpers import Helpers

class CollectorCore:
    pass
    __all__ = [Helpers, CDTEntitlements]
