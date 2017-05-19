# -*- coding: utf-8 -*-

from .frkl import (EnsurePythonObjectProcessor, EnsureUrlProcessor,
                   FrklProcessor, Jinja2TemplateProcessor,
                   LoadMoreConfigsProcessor, MergeProcessor, RegexProcessor,
                   ToYamlProcessor, UrlAbbrevProcessor, Frkl,
                   CHILD_MARKER_NAME, DEFAULT_LEAF_NAME, DEFAULT_LEAFKEY_NAME,
                   OTHER_KEYS_NAME, KEY_MOVE_MAP_NAME, FrklCallback)

__author__ = """Markus Binsteiner"""
__email__ = 'makkus@posteo.de'
__version__ = '0.1.0'
