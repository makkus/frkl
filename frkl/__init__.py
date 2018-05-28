# -*- coding: utf-8 -*-

__author__ = """Markus Binsteiner"""
__email__ = "makkus@posteo.de"
__version__ = "0.3.0"

from .frkl import Frkl, load_from_url_or_path
from .processors import (
    UrlAbbrevProcessor,
    EnsurePythonObjectProcessor,
    EnsureUrlProcessor,
    LoadMoreConfigsProcessor,
)
