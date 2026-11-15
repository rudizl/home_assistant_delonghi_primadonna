"""Load the integration's pure modules without Home Assistant.

The package __init__ imports Home Assistant, so a bare package object
is registered instead; protocol, const and machine_switch only use
the standard library.
"""
import sys
import types
from pathlib import Path

PACKAGE = 'delonghi_primadonna'
PATH = Path(__file__).parents[1] / 'custom_components' / PACKAGE

if PACKAGE not in sys.modules:
    module = types.ModuleType(PACKAGE)
    module.__path__ = [str(PATH)]
    sys.modules[PACKAGE] = module
