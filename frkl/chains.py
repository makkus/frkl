# -*- coding: utf-8 -*-

# python 3 compatibility
from __future__ import absolute_import, division, print_function, unicode_literals

from six import string_types
from frutils.defaults import JINJA_DELIMITER_PROFILES

from .defaults import *
from .processors import (
    EnsurePythonObjectProcessor,
    EnsureUrlProcessor,
    FrklProcessor,
    UrlAbbrevProcessor,
    Jinja2TemplateProcessor
)

# simple chain to convert a string (which might be an abbreviated url or path or yaml or json string) into a python object
LOAD_OBJECT_FROM_URL_CHAIN = [
    UrlAbbrevProcessor(),
    EnsureUrlProcessor(),
    EnsurePythonObjectProcessor(),
]

LOAD_STRING_FROM_URL_CHAIN = [
    UrlAbbrevProcessor(),
    EnsureUrlProcessor(),
]


# format of processor init dicts
BOOTSTRAP_FRKL_FORMAT = {
    STEM_KEY_NAME: "processors",
    DEFAULT_LEAF_KEY_NAME: "processor",
    DEFAULT_LEAF_DEFAULT_KEY_NAME: "type",
    OTHER_VALID_KEYS_NAME: ["init"],
    DEFAULT_LEAF_KEY_MAP_NAME: "init",
}

COLLECTOR_INIT_BOOTSTRAP_PROCESSOR_CHAIN = [FrklProcessor(**BOOTSTRAP_FRKL_FORMAT)]

# chain to bootstrap processor_chain in order to generate a frkl object
BOOTSTRAP_PROCESSOR_CHAIN = [
    UrlAbbrevProcessor(),
    EnsureUrlProcessor(),
    EnsurePythonObjectProcessor(),
    FrklProcessor(**BOOTSTRAP_FRKL_FORMAT),
]

def load_templated_string_from_url_chain(repl_dict, create_python_object=False, use_environment_vars=False, use_context=False, delimiter_profile=JINJA_DELIMITER_PROFILES["default"]):
    """Assemles a chain to load a file (local or remote) and replace templated values in it's content.

     Args:
        template_values (dict): a dictionary containing the values to replace template strings with
        create_python_object (bool): whether to return the string (False), or try to convert into python object (True)
        use_environment_vars (bool): whether to also use current environment variables  in the replacement dict. If True, it'll stored under the key 'LOCAL_ENV', if string, that will be used as key
        use_context (bool): whether to also use the frkl context in the replacement dict.  If True, it'll stored under the key 'frkl_vars', if string, that will be used as key
        delimiter_profile (dict): the jinja2 delimters

    Returns:
        str: the result string
    """

    template_processor = Jinja2TemplateProcessor(repl_dict, use_environment_vars=use_environment_vars, use_context=use_context, delimiter_profile=delimiter_profile)
    chain = LOAD_STRING_FROM_URL_CHAIN + [template_processor]
    if create_python_object:
        chain = chain + [EnsurePythonObjectProcessor()]

    return chain

