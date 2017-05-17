#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
test_frkl
----------------------------------

Tests for `frkl` module.
"""

import copy
import os
import pprint
import sys
import unittest
from contextlib import contextmanager

import pytest
import yaml

from frkl import cli, frkl

#from click.testing import CliRunner

TEST_DICTS = [({}, {}, {}), ({
    'a': 1
}, {
    'a': 1
}, {
    'a': 1
}), ({
    'a': 1
}, {
    'b': 1
}, {
    'a': 1,
    'b': 1
}), ({
    'a': 1
}, {
    'a': 2
}, {
    'a': 2
}), ({
    'a': 1,
    'aa': 11
}, {
    'b': 2,
    'bb': 22
}, {
    'a': 1,
    'aa': 11,
    'b': 2,
    'bb': 22
}), ({
    'a': 1,
    'aa': 11
}, {
    'b': 2,
    'aa': 22
}, {
    'a': 1,
    'b': 2,
    'aa': 22
})]

TEST_CONVERT_TO_PYTHON_OBJECT_DICT = [{
    "config": {
        "a": 1,
        "b": 2
    }
}, {
    "config": {
        "c": 3,
        "d": 4
    }
}]

TEST_CUSTOM_ABBREVS = {"test_abbr1": "https://example.url/folder1/folder2/"}

TEST_REGEXES = {
    "^start": "replacement",
    "frkl_expl": "makkus/freckles/examples"
}

TEST_REGEX_URLS = [("start_resturl", "replacement_resturl"), (
    "xstart_resturl", "xstart_resturl"), (
        "begin/frkl_expl/end", "begin/makkus/freckles/examples/end"), (
            "start/frkl_expl/end", "replacement/makkus/freckles/examples/end")]

TESTFILE_1_CONTENT = """- config:
    a: 1
    b: 2

- config:
    c: 3
    d: 4
"""

TEST_FRKLIZE_DICT_1 = [{
    "vars": {
        "aa": 11,
        "bb": 22
    },
    "task": {
        "task_name": "task1"
    }
}, {
    "vars": {
        "aa": 11,
        "bb": 22
    },
    "task": {
        "task_name": "task2"
    }
}]

TEST_FRKLIZE_1_RESULT = [{
    'task': {
        "task_name": 'task1'
    },
    'vars': {
        'a': 1,
        'b': 2,
        'aa': 11,
        'bb': 22
    }
}, {
    'task': {
        "task_name": 'task2'
    },
    'vars': {
        'a': 1,
        'b': 2,
        'cc': 33,
        'dd': 44
    }
}]

TEST_FRKLIZE_1_RESULT_DOUBLE = TEST_FRKLIZE_1_RESULT + TEST_FRKLIZE_1_RESULT

TEST_JINJA_DICT = {"config": {"a": 1, "b": 2, "c": 3, "d": 4}}
TEST_JINJA_URLS = [
    (os.path.join(
        os.path.dirname(os.path.realpath(__file__)), "testfile_jinja.yaml"),
     TEST_JINJA_DICT, TESTFILE_1_CONTENT),
]

TEST_ENSURE_FAIL_URLS = [("/tmp_does_not_exist/234234234"), (
    "https://raw222.githubusercontent.com/xxxxxxx8888/asdf.yml")]

TEST_PROCESSOR_CHAIN_1 = [
    frkl.RegexProcessor(TEST_REGEXES),
    frkl.UrlAbbrevProcessor(TEST_CUSTOM_ABBREVS)
]
TEST_CHAIN_1_URLS = [(["gh:makkus/freckles/examples/quickstart.yml"], [
    "https://raw.githubusercontent.com/makkus/freckles/master/examples/quickstart.yml"
]), (["bb:makkus/freckles/examples/quickstart.yml"], [
    "https://bitbucket.org/makkus/freckles/src/master/examples/quickstart.yml"
]), (["gh:frkl_expl/quickstart.yml"], [
    "https://raw.githubusercontent.com/makkus/freckles/master/examples/quickstart.yml"
])]

REGEX_CHAIN = [frkl.RegexProcessor(TEST_REGEXES)]
JINJA_CHAIN = [
    frkl.EnsureUrlProcessor(), frkl.Jinja2TemplateProcessor(
        template_values=TEST_JINJA_DICT)
]
ABBREV_CHAIN = [frkl.UrlAbbrevProcessor(abbrevs=TEST_CUSTOM_ABBREVS)]
ENSURE_URL_CHAIN = [frkl.EnsureUrlProcessor()]
ENSURE_PYTHON_CHAIN = [
    frkl.EnsureUrlProcessor(), frkl.EnsurePythonObjectProcessor()
]

FRKL_INIT_PARAMS = {
        "stem_key": "childs",
        "default_leaf_key": "task",
        "default_leaf_default_key": "task_name",
        "other_valid_keys": ["vars"],
        "default_leaf_key_map": "vars"
    }
FRKLIZE_CHAIN = [
    frkl.EnsureUrlProcessor(), frkl.EnsurePythonObjectProcessor(),
    frkl.LoadMoreConfigsProcessor(), frkl.FrklProcessor(FRKL_INIT_PARAMS)
]
ABBREV_FRKLIZE_CHAIN = [
    frkl.UrlAbbrevProcessor(), frkl.EnsureUrlProcessor(), frkl.EnsurePythonObjectProcessor(), frkl.LoadMoreConfigsProcessor(),
    frkl.FrklProcessor(FRKL_INIT_PARAMS)
]

PROCESSOR_TESTS = [
    (REGEX_CHAIN, "start_resturl", "unprocessed", ["replacement_resturl"]),
    (REGEX_CHAIN, "xstart_resturl", "unprocessed", ["xstart_resturl"]),
    (REGEX_CHAIN, "begin/frkl_expl/end", "unprocessed", ["begin/makkus/freckles/examples/end"]),
    (REGEX_CHAIN, "start/frkl_expl/end", "unprocessed", ["replacement/makkus/freckles/examples/end"]),
    (ENSURE_URL_CHAIN, os.path.join(os.path.dirname(os.path.realpath(__file__)), "testfile.yaml"), "unprocessed", [TESTFILE_1_CONTENT]),
    (ENSURE_URL_CHAIN, "https://raw.githubusercontent.com/makkus/frkl/master/tests/testfile.yaml", "unprocessed", [TESTFILE_1_CONTENT]),
    (ENSURE_PYTHON_CHAIN, os.path.join(os.path.dirname(os.path.realpath(__file__)), "testfile.yaml"),
           "unprocessed", [TEST_CONVERT_TO_PYTHON_OBJECT_DICT]),
    (ENSURE_PYTHON_CHAIN, "https://raw.githubusercontent.com/makkus/frkl/master/tests/testfile.yaml",
     "unprocessed", [TEST_CONVERT_TO_PYTHON_OBJECT_DICT]),
    (JINJA_CHAIN, os.path.join(os.path.dirname(os.path.realpath(__file__)), "testfile_jinja.yaml"),
     "unprocessed", [TESTFILE_1_CONTENT]),
    (ABBREV_CHAIN, "gh:makkus/freckles/examples/quickstart.yml", "unprocessed",
     ["https://raw.githubusercontent.com/makkus/freckles/master/examples/quickstart.yml"]),
    (ABBREV_CHAIN, "bb:makkus/freckles/examples/quickstart.yml", "unprocessed", ["https://bitbucket.org/makkus/freckles/src/master/examples/quickstart.yml"]),
    (FRKLIZE_CHAIN, os.path.join(os.path.dirname(os.path.realpath(__file__)), "testfile_frklize_1.yml"),
         "frkl", TEST_FRKLIZE_1_RESULT),
    (FRKLIZE_CHAIN, os.path.join(os.path.dirname(os.path.realpath(__file__)), "testfile_frklize_2.yml"),
     "frkl", TEST_FRKLIZE_1_RESULT),
    (FRKLIZE_CHAIN, os.path.join(os.path.dirname(os.path.realpath(__file__)), "testfile_frklize_3.yml"),
     "frkl", TEST_FRKLIZE_1_RESULT),
    (FRKLIZE_CHAIN, os.path.join(os.path.dirname(os.path.realpath(__file__)), "testfile_frklize_4.yml"),
     "frkl", TEST_FRKLIZE_1_RESULT_DOUBLE),
    (ABBREV_FRKLIZE_CHAIN, os.path.join(os.path.dirname(os.path.realpath(__file__)), "testfile_frklize_5.yml"),
     "frkl", TEST_FRKLIZE_1_RESULT_DOUBLE)
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


@pytest.mark.parametrize("processor, input_config, context_key, expected", PROCESSOR_TESTS)
def test_processor(processor, input_config, context_key, expected):

    frkl_obj = frkl.Frkl(input_config, processor_chain=processor)
    result_callback = frkl_obj.process()
    result = result_callback.result()

    pprint.pprint(result)
    print("XXX")
    pprint.pprint(expected)

    assert result == expected


@pytest.mark.parametrize("input_url", TEST_ENSURE_FAIL_URLS)
def test_ensure_fail_url_processor(input_url):

    prc = frkl.EnsureUrlProcessor()
    with pytest.raises(frkl.FrklConfigException):
        prc.process(input_url)

@pytest.mark.parametrize("config, expected", [
    ({"a": 1}, {"vars": {'a': 1}})
])
def test_frkl_valid_config(config, expected):

    frkl_obj = frkl.FrklProcessor(FRKL_INIT_PARAMS)
    frkl_obj.set_current_config(config)
    frkl_obj.process()

@pytest.mark.parametrize("config", [
    ({"a": 1, "vars": 2}),
    ({"tasks": 1, "childs": 1})
])
def test_frkl_invalid_config(config):

    frkl_obj = frkl.FrklProcessor(FRKL_INIT_PARAMS)
    frkl_obj.set_current_config(config)
    with pytest.raises(frkl.FrklConfigException):
        frkl_obj.process()


def test_frkl_yield():

    frkl_obj = frkl.FrklProcessor(FRKL_INIT_PARAMS)
    config_1 = {"vars": {"aa": 11}, "childs": [{"task": {"type": "test11"}, "vars": {"bb": 22}}]}
    config_2 = {"vars": {"a": 1}, "childs": [{"task": {"type": "test"}, "vars": {"b": 2}}, {"task": {"type": "another"}, "vars": {"c": 3}}, {"vars": {"d": 4}, "task": {"type": "3rd"}}]}
    config_0 = {"vars": {"eee": 444}}
    config_4 = {"vars": {"gg": 66}, "childs": [{"task": {"type": "test_NEW"}, "vars": {"bb": 22}}]}
    frkl_obj.set_current_config(config_1)
    frkl_obj.set_current_config(config_2)
    frkl_obj.set_current_config(config_0)
    frkl_obj.set_current_config(config_4)

    result = frkl_obj.process_config()

    # print(result)
    for i in result:
        print("---------------")
        pprint.pprint(i)
        print("---------------")
