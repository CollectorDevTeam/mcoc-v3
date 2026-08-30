"""
Auto-discover helper modules inside this package.
"""

import pkgutil
import importlib
import sys

# dynamic namespace
class CDTHelpers:
    pass

# discover all modules in this package
package = __name__
prefix = package + "."

for module_info in pkgutil.iter_modules(sys.modules[package].__path__, prefix):
    module = importlib.import_module(module_info.name)
    name = module_info.name.split(".")[-1]
    setattr(CDTHelpers, name, module)

__all__ = ["CDTHelpers"]
