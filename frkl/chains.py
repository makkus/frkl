# -*- coding: utf-8 -*-

# python 3 compatibility
from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

from .defaults import *
from .processors import UrlAbbrevProcessor, EnsureUrlProcessor, EnsurePythonObjectProcessor, FrklProcessor
# simple chain to convert a string (which might be an abbreviated url or path or yaml or json string) into a python object
DEFAULT_PROCESSOR_CHAIN = [
    UrlAbbrevProcessor(),
    EnsureUrlProcessor(),
    EnsurePythonObjectProcessor()
]

# format of processor init dicts
BOOTSTRAP_FRKL_FORMAT = {
    STEM_KEY_NAME: "processors",
    DEFAULT_LEAF_KEY_NAME: "processor",
    DEFAULT_LEAF_DEFAULT_KEY_NAME: "type",
    OTHER_VALID_KEYS_NAME: ["init"],
    DEFAULT_LEAF_KEY_MAP_NAME: "init"
}

COLLECTOR_INIT_BOOTSTRAP_PROCESSOR_CHAIN = [
    FrklProcessor(BOOTSTRAP_FRKL_FORMAT)
]

# chain to bootstrap processor_chain in order to generate a frkl object
BOOTSTRAP_PROCESSOR_CHAIN = [
    UrlAbbrevProcessor(),
    EnsureUrlProcessor(),
    EnsurePythonObjectProcessor(),
    FrklProcessor(BOOTSTRAP_FRKL_FORMAT)
]
