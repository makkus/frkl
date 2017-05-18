# -*- coding: utf-8 -*-

# python 3 compatibility
from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import abc
import collections
import contextlib
import copy
import itertools
import logging
import os
import pprint
import re
import sys
import types

import requests
import six
import yaml
from jinja2 import BaseLoader, Environment, PackageLoader
from six import string_types
from stevedore import driver

try:
    set
except NameError:
    from sets import Set as set

try:
    from urllib.request import urlopen
    from urllib.parse import urlparse
except ImportError:
    from urlparse import urlparse
    from urllib import urlopen

__metaclass__ = type

log = logging.getLogger("frkl")

FRKL_DEFAULT_PARAMS = {
        "stem_key": "childs",
        "default_leaf_key": "task",
        "default_leaf_default_key": "task_name",
        "other_valid_keys": ["vars"],
        "default_leaf_key_map": "vars"
    }

PLACEHOLDER = -9876
NO_STEM_INDICATOR = "-99999"
RECURSIVE_LOAD_INDICATOR = "-67323"

# abbreviations used by the UrlAbbrevProcessor class
DEFAULT_ABBREVIATIONS = {
    'gh':
    ["https://raw.githubusercontent.com", PLACEHOLDER, PLACEHOLDER, "master"],
    'bb': ["https://bitbucket.org", PLACEHOLDER, PLACEHOLDER, "src", "master"]
}

# ------------------------------------------------------------
# utility methods


def is_list_of_strings(input_obj):
    """Helper method to determine whether an object is a list or tuple of only strings (or string_types).

    Args:
      input_obj (object): the object in question

    Returns:
      bool: whether or not the object is a list of strings
    """

    return bool(input_obj) and isinstance(input_obj, (
        list, tuple)) and not isinstance(input_obj, string_types) and all(
            isinstance(item, string_types) for item in input_obj)


def dict_merge(dct, merge_dct, copy_dct=True):
    """ Recursive dict merge. Inspired by :meth:``dict.update()``, instead of
    updating only top-level keys, dict_merge recurses down into dicts nested
    to an arbitrary depth, updating keys. The ``merge_dct`` is merged into
    ``dct``.

    Copied from: https://gist.github.com/angstwad/bf22d1822c38a92ec0a9

    Args:
      dct (dict): dict onto which the merge is executed
      merge_dct (dict): dct merged into dct
    Kwargs:
      copy_dct (bool): whether to (deep-)copy dct before merging (and leaving it unchanged), or not (default: copy)

    Returns:
      dict: the merged dict (original or copied)
    """

    if copy_dct:
        dct = copy.deepcopy(dct)

    for k, v in merge_dct.items():
        if (k in dct and isinstance(dct[k], dict) and
                isinstance(merge_dct[k], collections.Mapping)):
            dict_merge(dct[k], merge_dct[k], copy_dct=False)
        else:
            dct[k] = merge_dct[k]

    return dct


CONFIG_PROCESSOR_VALUE_TYPES = ["STRING", "URL", "JSON", "YAML", "DICT"]


# extensions
# ------------------------------------------------------------------------
def load_extension(name, init_params=None):
    """Loading an extension.

    Args:
      name (str): the registered name of the extension
      init_params (dict): the parameters to initialize the extension object

    Returns:
      FrklConfig: the extension object
    """

    if not init_params:
        init_params = {}

    log2 = logging.getLogger("stevedore")
    out_hdlr = logging.StreamHandler(sys.stdout)
    out_hdlr.setFormatter(logging.Formatter('PLUGIN ERROR -> %(message)s'))
    out_hdlr.setLevel(logging.DEBUG)
    log2.addHandler(out_hdlr)
    log2.setLevel(logging.INFO)

    log.debug("Loading extension...")

    mgr = driver.DriverManager(
        namespace='frkl.frk',
        name=name,
        invoke_on_load=True,
        invoke_args=(init_params, ))
    log.debug("Registered plugins: {}".format(", ".join(
        ext.name for ext in mgr.extensions)))

    return mgr
    # return {ext.name: ext.plugin() for ext in mgr.extensions}

# ------------------------------------------------------------------------
# Frkl Exception(s)


class FrklConfigException(Exception):
    def __init__(self, message, errors=[]):
        """Exception that is thrown when processing configuration urls/content.

        Args:
          message (str): the error message
          errors (list): list of root causes and error descriptions
        """

        super(FrklConfigException, self).__init__(message)
        if isinstance(errors, Exception):
            self.errors = [errors]
        else:
            self.errors = errors


# ---------------------------------------------------------------------------
# configuration wrapper
class FrklConfig(list):

    def flatten(self):
        result = []
        for conf in self:
            result_dict = {}
            for var, value_dicts in conf.items():
                result_dict[var] = {}
                for value_dict in value_dicts:
                    dict_merge(result_dict[var], value_dict, copy_dct=False)
            result.append(result_dict)

        return result


@six.add_metaclass(abc.ABCMeta)
class ConfigProcessor(object):
    """Abstract base class for config url/content manipulators.

    In order to enable configuration urls and content to be written as quickly and minimal as possible, frkl supports pluggable processors that can manipulate the configuration urls and contents. For example, urls can be appbreviated 'gh' -> 'https://raw.githubusercontent.com/blahblah'.
    """

    def __init__(self, init_params={}):
        """
        Args:
          init_params (dict): arguments to initialize the processor
        """

        self.init_params = init_params

        msg = self.validate_init()
        if not msg == True:
            raise FrklConfigException(msg)

    def validate_init(self):
        """Optional method that can be overwritten to validate input arguments for this processor.
        """

        return True

    def set_current_config(self, input_config):
        """Sets the current configuration.

        Args:
          input_config (object): current configuration to be processed
        """

        self.current_input_config = input_config
        self.new_config()

    def new_config(self):
        """Can be overwritten to initially compute a new config after it is first set."""

        pass

    def process_config(self):
        """Kick of processing using the sub-classes 'process' method.

      Args:
        input_config (object): the configuration to process

      Returns:
        object: the processed configuration, if the return value is a tuple of size 2, the first element is the processed configuration, and the 2nd one is the (changed) list of configs
      """

        result = self.process()
        return result

    def get_additional_configs(self):
        """Returns additional configs if applicable.

        Returns:
          list: other configs to be processed next
        """

        return None

    def process(self):
        """Processes the config url or content.

        Args:
          input_config (object): input configuration url or content

        Returns:
          object: processed config url or content
        """

        return self.current_input_config


class EnsureUrlProcessor(ConfigProcessor):
    """Makes sure the provided string is a url"""

    def get_config(self, config_file_url):
        """Retrieves the config (if necessary), and returns its content.

        Config can be either a path to a local yaml file, an url to a remote yaml file, or a json string.

        Args:
          config_file_url (str): the url/path/json content
        """

        # check if file first
        if os.path.exists(config_file_url):
            log.debug("Opening as file: {}".format(config_file_url))
            with open(config_file_url) as f:
                content = f.read()

        # check if url
        elif config_file_url.startswith("http"):

            log.debug("Opening as url: {}".format(config_file_url))
            verify_ssl = True
            try:
                r = requests.get(config_file_url, verify=verify_ssl)
                r.raise_for_status()
                content = r.text
            except (Exception) as e:
                raise FrklConfigException(
                    "Could not retrieve configuration from: {}".format(
                        config_file_url), e)
        else:
            raise FrklConfigException(
                "Not a supported config file url or no local file found: {}".
                format(config_file_url))

        return content

    def process(self):

        result = self.get_config(self.current_input_config)
        return result


class EnsurePythonObjectProcessor(ConfigProcessor):
    """Makes sure the provided string is either valid yaml or json, and converts it into a str.
  """

    def process(self):

        config_obj = yaml.load(self.current_input_config)
        return config_obj


class FrklProcessor(ConfigProcessor):

    def __init__(self, init_params={}):
        self.init_params = init_params

        msg = self.validate_init()
        if not msg == True:
            raise FrklConfigException(msg)

        self.values_so_far = {}
        self.configs = []

    def validate_init(self):

        self.stem_key = self.init_params['stem_key']
        self.default_leaf_key = self.init_params['default_leaf_key']
        self.default_leaf_default_key = self.init_params[
            'default_leaf_default_key']
        self.other_valid_keys = self.init_params['other_valid_keys']
        self.default_leaf_key_map = self.init_params['default_leaf_key_map']
        if isinstance(self.default_leaf_key_map, string_types):
            self.default_leaf_key_map = {"*": self.default_leaf_key_map}
        elif isinstance(self.default_leaf_key_map, dict):
            self.default_leaf_key_map = self.default_leaf_key_map
        else:
            return "Type '{}' not supported for default leaf key map.".format(
                type(self.default_leaf_key_map))

        self.all_keys = set([self.stem_key, self.default_leaf_key])
        self.all_keys.update(self.other_valid_keys)

        self.break_key = self.init_params.get('break_key', None)
        self.break_marker = self.init_params.get('break_marker', None)

        return True

    def new_config(self):

        # make sure the new value is a dict, with only allowed keys
        if isinstance(self.current_input_config, (list, tuple)):
            self.configs.extend(self.current_input_config)
        else:
            self.configs.append(self.current_input_config)


    def process(self):

        result = self.frklize(self.current_input_config, self.values_so_far)

        return result


    def frklize(self, config, current_vars):


        # mkaing sure the new value is a dict, with only allowed keys
        if isinstance(config, string_types):
            config = {
                self.default_leaf_key: {
                    self.default_leaf_default_key: config
                }
            }

        if isinstance(config, (list, tuple)):
            for item in config:
                for result in self.frklize(item, copy.deepcopy(current_vars)):
                    yield result
        else:

            if not isinstance(config, dict):
                raise FrklConfigException(
                    "Not a supported type for value '{}': {}".format(
                        config, type(config)))

            new_value = {}

            # check whether any of the known keys is available here, if not,
            # we check whether ther is a default key registered for the name of the keys
            if not any(x in config.keys() for x in self.all_keys):

                if not len(config) == 1:
                    raise FrklConfigException("This form of configuration is not implemented yet")
                else:
                    key = next(iter(config))
                    value = config[key]

                    insert_leaf_key = self.default_leaf_key
                    insert_leaf_key_key = self.default_leaf_default_key
                    new_value.setdefault(insert_leaf_key, {})[insert_leaf_key_key] = key

                    if not isinstance(value, dict):
                        raise FrklConfigException("Non-dict values for default leaf key items not supported (yet?): {}".format(value))
                    if all(x in self.all_keys for x in value.keys()):
                        dict_merge(new_value, value, copy_dct=False)
                    elif all(x not in self.all_keys for x in value.keys()):
                        if key in self.default_leaf_key_map.keys():
                            migrate_key = self.default_leaf_key_map[key]
                        elif '*' in self.default_leaf_key_map.keys():
                            migrate_key = self.default_leaf_key_map['*']
                        else:
                            raise FrklConfigException("Can't find default_leaf_key to move values of key '{}".format(key))
                        new_value[migrate_key] = value

            else:
                # check whether all keys are allowed
                for key in config.keys():
                    if not key in self.all_keys:
                        raise FrklConfigException("Key '{}' not allowed, since it is an unknown keys amongst known keys in config: {}".format(key, config))

                new_value = config


            if self.stem_key in new_value.keys() and self.default_leaf_key in new_value.keys():
                raise FrklConfigException(
                    "Configuration can't have both stem key ({}) and default leaf key ({}) on the same level: {}".
                    format(self.stem_key, self.default_leaf_key, new_value))

            # at this point we have an 'expanded' dict

            stem_branch = new_value.pop(self.stem_key, NO_STEM_INDICATOR)
            # merge new values with current_vars
            dict_merge(current_vars, new_value, copy_dct=False)
            new_value = copy.deepcopy(current_vars)

            if stem_branch == NO_STEM_INDICATOR:
                if self.default_leaf_key in new_value.keys():
                    yield new_value

            else:
                for item in self.frklize(stem_branch, copy.deepcopy(current_vars)):
                    yield item


class Jinja2TemplateProcessor(ConfigProcessor):
    def __init__(self, template_values={}):
        self.template_values = template_values

    def process(self):

        rtemplate = Environment(loader=BaseLoader()).from_string(self.current_input_config)
        config_string = rtemplate.render(self.template_values)

        return config_string


class RegexProcessor(ConfigProcessor):
    def __init__(self, regexes):
        """Replaces all occurences of regex matches.

        Args:
          regexes (dict): a map of regexes and their replacements
        """

        self.regexes = regexes

    def process(self):

        new_config = self.current_input_config

        for regex, replacement in self.regexes.items():
            new_config = re.sub(regex, replacement, new_config)

        return new_config


class LoadMoreConfigsProcessor(ConfigProcessor):



    def process(self):

        if is_list_of_strings(self.current_input_config):
            return None
        else:
            return self.current_input_config


    def get_additional_configs(self):

        if is_list_of_strings(self.current_input_config):
            return self.current_input_config
        else:
            return None


class UrlAbbrevProcessor(ConfigProcessor):
    def __init__(self, abbrevs={}, add_default_abbrevs=True):
        """Replaces strings in an input configuration url with its expanded version.

        The default constructor without any arguments will create a processor only using the default, inbuilt abbreviations

        Kwargs:
          abbrevs (dict): custom abbreviations to use
          add_default_abbrevs (bool): whether to add the default abbreviations
        """

        if not abbrevs:
            if add_default_abbrevs:
                self.abbrevs = DEFAULT_ABBREVIATIONS
            else:
                self.abbrevs = {}
        else:
            if add_default_abbrevs:
                self.abbrevs = copy.deepcopy(DEFAULT_ABBREVIATIONS)
                dict_merge(self.abbrevs, abbrevs, copy_dct=False)
            else:
                self.abbrevs = copy.deepcopy(abbrevs)

    def process(self):

        result = self.expand_config(self.current_input_config)
        return result

    def expand_config(self, config):
        """Expands abbreviated configuration urls that start with `<token>:`.

        This is a convenience for the user, as they don't have to type out long urls if they don't want to.

        To make it easier to remember (and shorter to type) config urls, *frkl*
        supports abbreviations which will be replaced before attempting to load a
        configuration. In addition to inbuild abbreviations, a custom ones can be
        piped into the Frkl constructor. This needs to be a dictionary of string to
        string (abbreviation -> full url-part, eg. ``freckles_configs -->
        https://raw.githubusercontent.com/makkus/freckles/master/examples``, which
        would enable the user to provide this config url:
        ``freckles_config:quickstart.yml``) or string to list (abbreviation -> list
        of tokens to assemble the finished string, which for example for getting
        raw files from the master branch of a github repo would look like:
        ["https://raw.githubusercontent.com", frkl.PLACEHOLDER, frkl.PLACEHOLDER,
        "master] -- the input config ``gh:makkus/freckles/examples/quickstart.yml``
        would result in the same string as in the first example above -- this
        method is a bit more fragile, because the input string can't have less
        tokens seperated by '/' than the value list).

        Args:
          config (str): the configuration url/json/etc...

        Returns:
          str: the configuration with all occurances of registered abbreviations replaced

        """

        prefix, sep, rest = config.partition(':')

        if prefix in self.abbrevs.keys():

            if isinstance(self.abbrevs[prefix], string_types):
                return "{}{}".format(self.abbrevs[prefix], rest)
            else:
                tokens = rest.split("/")
                tokens_copy = copy.copy(tokens)

                min_tokens = self.abbrevs[prefix].count(PLACEHOLDER)

                result_string = ""
                for t in self.abbrevs[prefix]:

                    if t == PLACEHOLDER:
                        if not tokens:
                            raise FrklConfigException(
                                "Can't expand url '{}': not enough parts, need at least {} parts seperated by '/' after ':'".
                                format(config, min_tokens))
                        to_append = tokens.pop(0)
                        if not to_append:
                            raise FrklConfigException(
                                "Last token empty, can't expand: {}".format(
                                    tokens_copy))
                    else:
                        to_append = t

                    result_string += to_append
                    result_string += "/"

                if tokens:
                    postfix = "/".join(tokens)
                    result_string += postfix

                return result_string
        else:
            return config


DEFAULT_PROCESSOR_CHAIN = [
    UrlAbbrevProcessor(), EnsureUrlProcessor(), EnsurePythonObjectProcessor()
]

BOOTSTRAP_FRKL_FORMAT = {
    "stem_key": "processors",
    "default_leaf_key": "processor",
    "default_leaf_default_key": "type",
    "other_valid_keys": ["init"],
    "default_leaf_key_map": "init"
}
BOOTSTRAP_PROCESSOR_CHAIN = [
    UrlAbbrevProcessor(), EnsureUrlProcessor(), EnsurePythonObjectProcessor(),
    FrklProcessor(BOOTSTRAP_FRKL_FORMAT)
]

# ----------------------------------------------------------------
class MergeResultCallback(object):

    def __init__(self):
        self.result_list = []

    def callback(self, process_result):
        self.result_list.append(process_result)

    def result(self):
        return self.result_list

class FrklFactoryCallback(object):

    def __init__(self):
        self.processors = []
        self.bootstrap_chain = []

    def callback(self, item):
        self.processors.append(item)

        ext_name = item.get('processor', {}).get('name', None)
        if not ext_name:
            raise FrklConfigException(
                "Can't parse processor name using config: {}".format(item))
        ext_init_params = item.get('init', {})
        log.debug("Loading extension '{}' using init parameters: '{}".
                  format(ext_name, ext_init_params))
        ext = load_extension(ext_name, ext_init_params)
        self.bootstrap_chain.append(ext.driver)

    def result(self):

        return Frkl([], self.bootstrap_chain)

class Frkl(object):

    def factory(bootstrap_configs, frkl_configs=[]):

        bootstrap = Frkl(bootstrap_configs, BOOTSTRAP_PROCESSOR_CHAIN)
        config_frkl = bootstrap.process(FrklFactoryCallback()).result()

        config_frkl.set_configs(frkl_configs)
        return config_frkl

    factory = staticmethod(factory)

    def __init__(self, configs=[], processor_chain=DEFAULT_PROCESSOR_CHAIN):
        """Base object that holds the configuration.

        Args:
          configs (list): list of configurations, will be processed in the order they come in
        Kwargs:
          stem_key (str): the key that is used to travers a level up in the configuration, generating 'child' configs
          other_valid_keys (list): list of keynames that are valid config 'holders'
          processor_chain (list): processor chain to use, defaults to [:class:`UrlAbbrevProcessor`]

        Returns:
          str: the final config url, all abbreviations replaced
        """

        if not isinstance(processor_chain, (list, tuple)):
            processor_chain = [processor_chain]
        self.processor_chain = processor_chain

        self.configs = []
        self.set_configs(configs)

    def set_configs(self, configs):
        """Sets the configuration(s) for this Frkl object.

        Args:
          configs (list): the configurations, will wrapped in a list if not a list or tuple already
        """

        if not isinstance(configs, (list, tuple)):
            configs = [configs]

        self.configs = list(configs)

    def append_configs(self, configs):
        """Appends the provided configuration(s) for this Frkl object.

        Args:
          configs (list): the configurations, will wrapped in a list if not a list or tuple already
        """

        if not isinstance(configs, (list, tuple)):
            configs = [configs]

        # ensure configs are wrapped
        for c in configs:
            self.configs.append(c)


    def process(self, callback=None):

        if not callback:
            callback = MergeResultCallback()

        self.process_configs(self.configs, callback)

        return callback

    def process_configs(self, configs, callback):
        """Kicks off the processing of the configuration urls.

      Args:
        configs (list): the configs to process

      Returns:
        list: a list of configuration items, corresponding to the input configuration urls
      """

        idx = 0

        configs_copy = copy.deepcopy(configs)

        while configs_copy:

            if len(configs_copy) > 1024:
                raise FrklConfigException("More than 1024 configs, this looks like a loop, exiting.")

            config = configs_copy.pop(0)

            self.process_single_config(config, self.processor_chain, callback, configs_copy)



    def process_single_config(self, config, processor_chain, callback, configs_copy):

        if not config:
            return

        if not processor_chain:
            callback.callback(config)
            return

        current_processor = processor_chain[0]
        current_processor.set_current_config(copy.deepcopy(config))
        additional_configs = current_processor.get_additional_configs()
        if additional_configs:
            configs_copy[0:0] = additional_configs

        last_processing_result = current_processor.process_config()
        if isinstance(last_processing_result, types.GeneratorType):
            for item in last_processing_result:
                self.process_single_config(item, processor_chain[1:], callback, configs_copy)
        else:
            self.process_single_config(last_processing_result, processor_chain[1:], callback, configs_copy)


    def frkl(self):
        """Returns a flattened list of a frklized config chain.

        Returns:
        list: a list of expanded config items
        """

        result = self.process()
        return result.result()


    def get_config(config):
        """Retrieves the configuration, including pre-processing.

        Args:
          config (str): the configuration url/json/etc...

        Returns:
          dict: the pre-processed configuration dict
        """

        if isinstance(config, dict):
            log.debug("Not processing config, already dict: {}".format(config))
            return config

        # expanding configuration url if applicable

        if os.path.exists(config):
            log.debug("Opening as file: {}".format(config))
            with open(config_file_url) as f:
                content = f.read()

    def frklize_config(self, root, configs):
        """Read all configs in order, generate a composite.

        Args:
          root (list): root list to add new configurations onto
          configs (list): configurations to add
        """

        for c in configs:

            self.get_config(c)
