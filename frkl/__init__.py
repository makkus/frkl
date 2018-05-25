# -*- coding: utf-8 -*-

__author__ = """Markus Binsteiner"""
__email__ = "makkus@posteo.de"
__version__ = "0.3.0"

from .frkl import Frkl
from .processors import (
    UrlAbbrevProcessor,
    EnsurePythonObjectProcessor,
    EnsureUrlProcessor,
    LoadMoreConfigsProcessor,
)
