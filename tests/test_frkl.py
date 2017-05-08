#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
test_frkl
----------------------------------

Tests for `frkl` module.
"""


import pprint
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

TEST_CONVERT_TO_PYTHON_OBJECT_DICT = [
    {"config":
     {"a": 1, "b": 2}},
    {"config":
     {"c": 3, "d": 4}}
]

TEST_CUSTOM_ABBREVS = {
    "test_abbr1": "https://example.url/folder1/folder2/"
}

TEST_ABBREV_URLS = [
    # ("gh:makkus/freckles/examples/quickstart.yml", "https://raw.githubusercontent.com/makkus/freckles/master/examples/quickstart.yml"),
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

TESTFILE_1_CONTENT = """- config:
    a: 1
    b: 2

- config:
    c: 3
    d: 4
"""

TEST_ENSURE_URLS = [
    (os.path.join(os.path.dirname(os.path.realpath(__file__)), "testfile.yaml"), TESTFILE_1_CONTENT),
    ("https://raw.githubusercontent.com/makkus/frkl/master/tests/testfile.yaml", TESTFILE_1_CONTENT)
]

TEST_FRKLIZE_DICT_1 = [{
    "vars": {
        "aa": 11,
        "bb": 22
        },
    "task": {
        "task_name": "task1"
    }}, {
    "vars": {
        "aa": 11,
        "bb": 22
        },
    "task": {
        "task_name": "task2"
    }}]

TEST_FRKLIZE_URLS = [
    (os.path.join(os.path.dirname(os.path.realpath(__file__)), "testfile_frklize_1.yml"), TEST_FRKLIZE_DICT_1),
    (os.path.join(os.path.dirname(os.path.realpath(__file__)), "testfile_frklize_2.yml"), TEST_FRKLIZE_DICT_1)
]

TEST_FRKLIZE_1_RESULT = [
    {'task': {"task_name": 'task1'},
     'vars': {'a': 1, 'b': 2, 'aa': 11, 'bb': 22}
    },
    {'task': {"task_name": 'task2'},
     'vars': {'a': 1, 'b': 2, 'cc': 33, 'dd': 44}
    }
]

TEST_JINJA_DICT = {
    "config": {
      "a": 1,
      "b": 2,
      "c": 3,
      "d": 4
    }
}
TEST_JINJA_URLS = [
    (os.path.join(os.path.dirname(os.path.realpath(__file__)), "testfile_jinja.yaml"), TEST_JINJA_DICT, TESTFILE_1_CONTENT),
]

TEST_ENSURE_FAIL_URLS = [
    ("/tmp_does_not_exist/234234234"),
    ("https://raw222.githubusercontent.com/xxxxxxx8888/asdf.yml")
]

TEST_PROCESSOR_CHAIN_1 = [frkl.RegexProcessor(TEST_REGEXES), frkl.UrlAbbrevProcessor(TEST_CUSTOM_ABBREVS)]
TEST_CHAIN_1_URLS = [
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

@pytest.mark.parametrize("input_url, env, expected", TEST_JINJA_URLS)
def test_process_jinja(input_url, env, expected):

    prc = frkl.Jinja2TemplateProcessor(template_values=env)
    chain = [frkl.EnsureUrlProcessor(), prc]
    result = frkl.process_chain([input_url], chain)

    assert result[0] == expected


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

@pytest.mark.parametrize("input_url, expected", TEST_ENSURE_URLS)
def test_ensure_processor(input_url, expected):

    prc = frkl.EnsureUrlProcessor()
    result = prc.process(input_url)

    assert result == expected

@pytest.mark.parametrize("input_url, expected", TEST_ENSURE_URLS)
def test_ensure_python_object_processor(input_url, expected):

    prc = frkl.EnsurePythonObjectProcessor()
    chain = [frkl.EnsureUrlProcessor(), prc]
    result = frkl.process_chain([input_url], chain)

    assert result[0] == TEST_CONVERT_TO_PYTHON_OBJECT_DICT


@pytest.mark.parametrize("input_url", TEST_ENSURE_FAIL_URLS)
def test_ensure_fail_processor(input_url):

    prc = frkl.EnsureUrlProcessor()
    with pytest.raises(frkl.FrklConfigException):
        prc.process(input_url)


@pytest.mark.parametrize("input_urls, expected", TEST_CHAIN_1_URLS)
def test_config_chain_processors(input_urls, expected):

    f = frkl.Frkl(input_urls, processor_chain=TEST_PROCESSOR_CHAIN_1)

    assert f.configs == expected

@pytest.mark.parametrize("input_url, expected_dict", TEST_FRKLIZE_URLS)
def test_frklize_processor(input_url, expected_dict):

    registered_defaults = "vars"
    prc = frkl.FrklDictProcessor("childs", "task", "task_name", ["vars"], registered_defaults)
    chain = [frkl.EnsureUrlProcessor(), frkl.EnsurePythonObjectProcessor(), prc]
    result = frkl.process_chain([input_url], chain)

    result_configs = result[0].flatten()

    assert result_configs == TEST_FRKLIZE_1_RESULT
