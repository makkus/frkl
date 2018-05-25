#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
test_frkl
----------------------------------

Tests for `frkl` module.
"""

import pprint

import pytest
import yaml
from frutils.frutils import *

from frkl.frkl import *
from frkl.frkl_factory import *
from frkl.callbacks import *
from frkl.processors import *

# from click.testing import CliRunner

TEST_DICTS = [({}, {}, {}),
              ({'a': 1}, {'a': 1}, {'a': 1}),
              ({'a': 1}, {'b': 1}, {'a': 1, 'b': 1}),
              ({'a': 1}, {'a': 2}, {'a': 2}),
              ({'a': 1, 'aa': 11}, {'b': 2, 'bb': 22}, {'a': 1, 'aa': 11, 'b': 2, 'bb': 22}),
              ({'a': 1, 'aa': 11}, {'b': 2, 'aa': 22}, {'a': 1, 'b': 2, 'aa': 22})
              ]

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
    RegexProcessor({"regexes": TEST_REGEXES}),
    UrlAbbrevProcessor({"abbrevs": TEST_CUSTOM_ABBREVS})
]
TEST_CHAIN_1_URLS = [(["gh:makkus/freckles/examples/quickstart.yml"], [
    "https://raw.githubusercontent.com/makkus/freckles/master/examples/quickstart.yml"
]), (["bb:makkus/freckles/examples/quickstart.yml"], [
    "https://bitbucket.org/makkus/freckles/src/master/examples/quickstart.yml"
]), (["gh:frkl_expl/quickstart.yml"], [
    "https://raw.githubusercontent.com/makkus/freckles/master/examples/quickstart.yml"
])]

REGEX_CHAIN = [RegexProcessor({"regexes": TEST_REGEXES})]
JINJA_CHAIN = [
    EnsureUrlProcessor(), Jinja2TemplateProcessor(
        {"template_values": TEST_JINJA_DICT})
]
ABBREV_CHAIN = [UrlAbbrevProcessor({"abbrevs": TEST_CUSTOM_ABBREVS})]
ENSURE_URL_CHAIN = [EnsureUrlProcessor()]
ENSURE_PYTHON_CHAIN = [
    EnsureUrlProcessor(), EnsurePythonObjectProcessor()
]

FRKL_INIT_PARAMS = {
    STEM_KEY_NAME: "childs",
    DEFAULT_LEAF_KEY_NAME: "task",
    DEFAULT_LEAF_DEFAULT_KEY_NAME: "task_name",
    DEFAULT_LEAF_KEY_MAP_NAME: "vars"
}
FRKLIZE_CHAIN = [
    EnsureUrlProcessor(), EnsurePythonObjectProcessor(),
    LoadMoreConfigsProcessor(), FrklProcessor(FRKL_INIT_PARAMS)
]
ABBREV_FRKLIZE_CHAIN = [
    UrlAbbrevProcessor(), EnsureUrlProcessor(), EnsurePythonObjectProcessor(), LoadMoreConfigsProcessor(),
    FrklProcessor(FRKL_INIT_PARAMS)
]

PROCESSOR_TESTS = [
    (REGEX_CHAIN, "start_resturl", "unprocessed", ["replacement_resturl"]),
    (REGEX_CHAIN, "xstart_resturl", "unprocessed", ["xstart_resturl"]),
    (REGEX_CHAIN, "begin/frkl_expl/end", "unprocessed", ["begin/makkus/freckles/examples/end"]),
    (REGEX_CHAIN, "start/frkl_expl/end", "unprocessed", ["replacement/makkus/freckles/examples/end"]),
    (ENSURE_URL_CHAIN, os.path.join(os.path.dirname(os.path.realpath(__file__)), "testfile.yaml"), "unprocessed",
     [TESTFILE_1_CONTENT]),
    (ENSURE_URL_CHAIN, "https://raw.githubusercontent.com/makkus/frkl/master/tests/testfile.yaml", "unprocessed",
     [TESTFILE_1_CONTENT]),
    (ENSURE_PYTHON_CHAIN, os.path.join(os.path.dirname(os.path.realpath(__file__)), "testfile.yaml"),
     "unprocessed", [TEST_CONVERT_TO_PYTHON_OBJECT_DICT]),
    (ENSURE_PYTHON_CHAIN, "https://raw.githubusercontent.com/makkus/frkl/master/tests/testfile.yaml",
     "unprocessed", [TEST_CONVERT_TO_PYTHON_OBJECT_DICT]),
    (JINJA_CHAIN, os.path.join(os.path.dirname(os.path.realpath(__file__)), "testfile_jinja.yaml"),
     "unprocessed", [TESTFILE_1_CONTENT]),
    (ABBREV_CHAIN, "gh:makkus/freckles/examples/quickstart.yml", "unprocessed",
     ["https://raw.githubusercontent.com/makkus/freckles/master/examples/quickstart.yml"]),
    (ABBREV_CHAIN, "bb:makkus/freckles/examples/quickstart.yml", "unprocessed",
     ["https://bitbucket.org/makkus/freckles/src/master/examples/quickstart.yml"]),
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


@pytest.mark.parametrize("processor, input_config, context_key, expected", PROCESSOR_TESTS)
def test_processor(processor, input_config, context_key, expected):
    frkl_obj = Frkl(input_config, processor_chain=processor)
    result = frkl_obj.process()

    pprint.pprint(result)
    print("XXX")
    pprint.pprint(expected)

    assert result == expected


@pytest.mark.parametrize("input_url", TEST_ENSURE_FAIL_URLS)
def test_ensure_fail_url_processor(input_url):
    prc = EnsureUrlProcessor()
    prc.set_current_config(input_url, {"last_call": False})
    with pytest.raises(FrklConfigException):
        prc.process()


@pytest.mark.parametrize("config, expected", [
    ({"a": 1}, {"vars": {'a': 1}})
])
def test_frkl_valid_config(config, expected):
    frkl_obj = FrklProcessor(FRKL_INIT_PARAMS)
    frkl_obj.set_current_config(config, {"last_call": False})
    frkl_obj.process()


@pytest.mark.parametrize("config", [
    ({"a": 1, "vars": 2}),
    ({"tasks": 1, "childs": 1})
])
def test_frkl_invalid_config(config):
    frkl_obj = FrklProcessor(FRKL_INIT_PARAMS)
    frkl_obj.set_current_config(config, {"last_call": False})
    with pytest.raises(FrklConfigException):
        for i in frkl_obj.process():
            print(i)


@pytest.mark.parametrize("test_name", [
    "simple_test",
    "simple_test2",
    "simple_test3",
    "simple_test4",
    "simple_test5",
    "simple_test6",
    "simple_test7",
    "simple_test8",
    # "simple_test9",
    # "simple_test10",
    "simple_test11",
    "load_single_config_test",
    "load_multiple_configs_test",
    "download_multiple_configs_test",
    "jinja_test",
    "jinja_test_2",
    "two_input_files_1"
])
def test_files(test_name):
    folder = os.path.join(os.path.dirname(os.path.realpath(__file__)), "test_dirs", test_name)
    chain_file = os.path.join(folder, "_chain.yml")
    input_files = []
    for child in os.listdir(folder):
        if not child.startswith("_"):
            input_files.append(os.path.join(folder, child))
    input_files.sort()
    pprint.pprint(input_files)
    result_file = os.path.join(folder, "__result.yml")

    with open(result_file) as f:
        content = f.read()

    expected_obj = yaml.load(content)

    frkl_obj = factory(chain_file, input_files)
    result_obj = frkl_obj.process()

    # pprint.pprint(expected_obj)
    # print("XXX")
    pprint.pprint(result_obj)

    assert expected_obj == result_obj


@pytest.mark.parametrize("test_name", [
    "simple_test12"
])
def test_files_collector(test_name):
    folder = os.path.join(os.path.dirname(os.path.realpath(__file__)), "test_dirs", test_name)
    chain_file = os.path.join(folder, "_chain.yml")
    input_files = []
    for child in os.listdir(folder):
        if not child.startswith("_"):
            input_files.append(os.path.join(folder, child))
    input_files.sort()
    pprint.pprint(input_files)
    result_file = os.path.join(folder, "__result.yml")

    with open(result_file) as f:
        content = f.read()

    expected_obj = yaml.load(content)

    frkl_obj = factory(chain_file, input_files)
    test12_init = {"append_keys": "vars/a"}
    result_obj = frkl_obj.process(MergeDictResultCallback(test12_init))

    # pprint.pprint(expected_obj)
    # print("XXX")
    pprint.pprint(result_obj)

    assert expected_obj == result_obj


@pytest.mark.parametrize("test_name", [
    "collector_1",
    "collector_2",
    "collector_3"
])
def test_collector_init(test_name):
    folder = os.path.join(os.path.dirname(os.path.realpath(__file__)), "test_dirs", test_name)

    input_files = []
    for child in os.listdir(folder):
        if not child.startswith("_"):
            input_files.append(os.path.join(folder, child))
    input_files.sort()

    result_file = os.path.join(folder, "__result.yml")

    with open(result_file) as f:
        content = f.read()

    expected_obj = yaml.load(content)

    init_file = os.path.join(folder, "_init.yml")
    result_obj = FrklCallback.init(init_file, input_files)
    result = result_obj.result()

    pprint.pprint(expected_obj)
    print("XXX")
    pprint.pprint(result)

    assert expected_obj == result
