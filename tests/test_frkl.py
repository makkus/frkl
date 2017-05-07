#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
test_frkl
----------------------------------

Tests for `frkl` module.
"""


import sys
import unittest
from contextlib import contextmanager
#from click.testing import CliRunner

import pytest

import os
import yaml

import copy

from frkl import frkl
from frkl import cli

TEST_DICTS = [
    ({}, {}, {}),
    ({'a': 1}, {'a': 1}, {'a': 1}),
    ({'a': 1}, {'b': 1}, {'a': 1, 'b':1} ),
    ({'a': 1}, {'a': 2}, {'a': 2}),
    ({'a': 1, 'aa': 11}, {'b': 2, 'bb': 22}, {'a': 1, 'aa': 11, 'b': 2, 'bb': 22}),
    ({'a': 1, 'aa': 11}, {'b': 2, 'aa': 22}, {'a': 1, 'b': 2, 'aa': 22})
]

TEST_CUSTOM_ABBREVS = {
    "test_abbr1": "https://example.url/folder1/folder2/"
}

TEST_ABBREV_URLS = [
    ("gh:makkus/freckles/examples/quickstart.yml", "https://raw.githubusercontent.com/makkus/freckles/master/examples/quickstart.yml"),
    ("bb:makkus/freckles/examples/quickstart.yml", "https://bitbucket.org/makkus/freckles/src/master/examples/quickstart.yml"),
    ("test_abbr1:file1", "https://example.url/folder1/folder2/file1")
]

TEST_REGEXES = {
    "^start": "replacement",
    "frkl_expl": "makkus/freckles/examples"
}

TEST_REGEX_URLS = [
    ("start_resturl", "replacement_resturl"),
    ("xstart_resturl", "xstart_resturl"),
    ("begin/frkl_expl/end", "begin/makkus/freckles/examples/end"),
    ("start/frkl_expl/end", "replacement/makkus/freckles/examples/end")
]

TEST_PROCESSOR_CHAIN = [frkl.RegexProcessor(TEST_REGEXES), frkl.UrlAbbrevProcessor(TEST_CUSTOM_ABBREVS)]

TEST_CHAIN_URLS = [
    (["gh:makkus/freckles/examples/quickstart.yml"], ["https://raw.githubusercontent.com/makkus/freckles/master/examples/quickstart.yml"]),
    (["bb:makkus/freckles/examples/quickstart.yml"], ["https://bitbucket.org/makkus/freckles/src/master/examples/quickstart.yml"]),
    (["gh:frkl_expl/quickstart.yml"], ["https://raw.githubusercontent.com/makkus/freckles/master/examples/quickstart.yml"])
]

@pytest.mark.parametrize("dict1, dict2, expected", TEST_DICTS)
def test_dict_merge_copy_result(dict1, dict2, expected):

    dict1_orig = copy.deepcopy(dict1)
    dict2_orig = copy.deepcopy(dict2)
    merged = frkl.dict_merge(dict1, dict2, True)
    assert merged == expected
    assert dict1 == dict1_orig
    assert dict2 == dict2_orig

@pytest.mark.parametrize("dict1, dict2, expected", TEST_DICTS)
def test_dict_merge_dont_copy_result(dict1, dict2, expected):

    dict1_orig = copy.deepcopy(dict1)
    dict2_orig = copy.deepcopy(dict2)
    merged = frkl.dict_merge(dict1, dict2, False)
    assert merged == expected
    assert dict1 == expected
    assert dict2 == dict2_orig

@pytest.mark.parametrize("input_url, expected", TEST_ABBREV_URLS)
def test_expand_config(input_url, expected):

    prc = frkl.UrlAbbrevProcessor(abbrevs=TEST_CUSTOM_ABBREVS)
    result = prc.process(input_url)

    assert result == expected

@pytest.mark.parametrize("input_url, expected", TEST_REGEX_URLS)
def test_regex_processor(input_url, expected):

    prc = frkl.RegexProcessor(TEST_REGEXES)
    result = prc.process(input_url)

    assert result == expected



@pytest.mark.parametrize("input_urls, expected", TEST_CHAIN_URLS)
def test_config_chain_processors(input_urls, expected):

    f = frkl.Frkl(input_urls, processor_chain=TEST_PROCESSOR_CHAIN)

    assert f.configs == expected

