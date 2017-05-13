# -*- coding: utf-8 -*-

# python 3 compatibility
from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import abc
import contextlib
import copy
import logging
import os
import pprint
import re
import sys

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

PLACEHOLDER = -9876
NO_STEM_INDICATOR = "-99999"
RECURSIVE_LOAD_INDICATOR = "-67323"

DEFAULT_ABBREVIATIONS = {
    'gh':
    ["https://raw.githubusercontent.com", PLACEHOLDER, PLACEHOLDER, "master"],
    'bb': ["https://bitbucket.org", PLACEHOLDER, PLACEHOLDER, "src", "master"]
}

# ------------------------------------------------------------
# utility methods


def is_list_of_strings(input_obj):

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


# ------------------------------------------------------------------------
# Processing configuration(s)
class ProcessResult(object):

    def __init__(self, processed_config, more_configs=[]):

        self.processed_config = processed_config
        self.more_configs = more_configs

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

    def process_config(self, input_config, current_context):
        """Kick of processing using the sub-classes 'process' method.

      Args:
        input_config (object): the configuration to process
        current_context (dict): (optional) current context, containing information about previously processed configurations

      Returns:
        object: the processed configuration, if the return value is a tuple of size 2, the first element is the processed configuration, and the 2nd one is the (changed) list of configs
      """

        result = self.process(input_config)
        if not isinstance(result, ProcessResult):
            return ProcessResult(result)
        else:
            return result

    @abc.abstractmethod
    def process(self, input_config, current_context={}):
        """Processes the config url or content.

        Args:
          input_config (object): input configuration url or content
          current_context (dict): (optional) current context, containing information about previously processed configurations

        Returns:
          object: processed config url or content
        """

        # raise Exception("Base ConfigProcess is not supposed to execute process method")


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

    def process(self, input_config):

        result = self.get_config(input_config)
        return result


class EnsurePythonObjectProcessor(ConfigProcessor):
    """Makes sure the provided string is either valid yaml or json, and converts it into a str.
  """

    def process(self, input_config):

        config_obj = yaml.load(input_config)
        return config_obj


class FrklDictProcessor(ConfigProcessor):
    """Expands an elastic dict.
  """

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

        return True

    def process(self, input_config):
        root = FrklConfig()
        self.frklize(input_config, root=root)

        return root

    def frklize(self, new_value, root=[], values_so_far_parent={}):

        values_so_far = copy.deepcopy(values_so_far_parent)

        # mkaing sure the new value is a dict, with only allowed keys
        if isinstance(new_value, string_types):
            new_value = {
                self.default_leaf_key: {
                    self.default_leaf_default_key: new_value
                }
            }
        elif isinstance(new_value, (list, tuple)):
            for item in new_value:
                self.frklize(item, root, values_so_far)
            return

        if not isinstance(new_value, dict):
            raise FrklConfigException(
                "Not a supported type for value '{}': {}".format(
                    new_value, type(new_value)))

        # we check whether any of the known keys is available here, if not,
        # we check whether there is a default key registered for the name (single) key
        if not any(x in new_value.keys() for x in self.all_keys):
            # if there are more than one keys in this, it's difficult to figure out what to do here, so for now let's just not allow that
            # if len(new_value.keys()) != 1:
            # raise FrklConfigException("If not using the full config format, leaf nodes are only allowed to have one key: {}".format(new_value))

            # the string value of the key, this will be end up as the default_leaf_default_key of the default_leaf_key
            key = list(new_value.keys())[0]

            # we need to know where to put the value of this, if it's not registered beforehand we raise an exception
            if not isinstance(new_value[key], dict) or not any(
                    x in new_value[key].keys() for x in self.all_keys):
                if not key in self.default_leaf_key_map.keys(
                ) and not '*' in self.default_leaf_key_map.keys():
                    raise FrklConfigException(
                        "Can't find registered default key and value for shortcut value: {}".
                        format(key))

                # if the current value is not a dict, we'll put it there, using the registered default value for this string
                if not key in self.default_leaf_key_map.keys():
                    insert_default_leaf_key = self.default_leaf_key_map['*']
                else:
                    insert_default_leaf_key = self.default_leaf_key_map[key]
                new_value[key] = {insert_default_leaf_key: new_value[key]}

            # if the keys of the (now) dict contain any of the allowed keys, we use the dict directly
            # TODO: check for 'unallowed' keys?
            if any(x in new_value[key].keys() for x in self.all_keys):
                temp_new_value = new_value[key]
                dict_merge(
                    temp_new_value, {
                        self.default_leaf_key: {
                            self.default_leaf_default_key: key
                        }
                    },
                    copy_dct=False)
                new_value = temp_new_value
            # else we put the whole dict under the default_leaf_key
            else:
                temp_new_value = {
                    self.default_leaf_key: {
                        self.default_leaf_default_key: key
                    }
                }
                dict_merge(
                    temp_new_value,
                    {self.default_leaf_default_key: new_value[key]},
                    copy_dct=False)
                new_value = temp_new_value

        if self.stem_key in new_value.keys(
        ) and self.default_leaf_key in new_value.keys():
            raise FrklConfigException(
                "Configuration can't have both stem key ({}) and default leaf key ({}) on the same level: {}".
                format(self.stem_key, self.default_leaf_key, new_value))

        stem = new_value.pop(self.stem_key, NO_STEM_INDICATOR)

        temp = {}
        dict_merge(temp, values_so_far, copy_dct=False)
        dict_merge(temp, new_value, copy_dct=False)
        new_value = temp

        for key in new_value.keys():
            if key not in self.all_keys:
                raise FrklConfigException(
                    "Key '{}' not allowed (in {})".format(key, new_value))

            values_so_far.setdefault(key, []).append(new_value[key])

        if stem == NO_STEM_INDICATOR:
            if self.default_leaf_key in new_value:
                root.append(values_so_far)
            return
        elif isinstance(stem,
                        (list, tuple)) and not isinstance(stem, string_types):
            self.frklize(stem, root, values_so_far)
        else:
            raise FrklConfigException("Value of {} must be list (is: '{}')".
                                      format(self.stem_key, type(stem)))


class Jinja2TemplateProcessor(ConfigProcessor):
    def __init__(self, template_values={}):
        self.template_values = template_values

    def process(self, input_config, context={}):

        rtemplate = Environment(loader=BaseLoader()).from_string(input_config)
        config_string = rtemplate.render(self.template_values)

        return config_string


class RegexProcessor(ConfigProcessor):
    def __init__(self, regexes):
        """Replaces all occurences of regex matches.

        Args:
          regexes (dict): a map of regexes and their replacements
        """

        self.regexes = regexes

    def process(self, input_config):

        new_config = input_config

        for regex, replacement in self.regexes.items():
            new_config = re.sub(regex, replacement, new_config)

        return new_config


class LoadMoreConfigsProcessor(ConfigProcessor):
    def process(self, input_config):

        if isinstance(input_config, (list, tuple)):
            if all(isinstance(item, string_types) for item in input_config):
                return ProcessResult(None, input_config)

        return input_config


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

    def process(self, input_config):

        result = self.expand_config(input_config)
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
    FrklDictProcessor(BOOTSTRAP_FRKL_FORMAT)
]

# ----------------------------------------------------------------


class Frkl(object):
    def factory(bootstrap_configs, frkl_configs=[]):

        bootstrap = Frkl(bootstrap_configs, BOOTSTRAP_PROCESSOR_CHAIN)

        prc_chain_config = bootstrap.process(result_key='flattened')
        bootstrap_chain = []
        for item in prc_chain_config:
            ext_name = item.get('processor', {}).get('name', None)
            if not ext_name:
                raise FrklConfigException(
                    "Can't parse processor name using config: {}".format(item))
            ext_init_params = item.get('init', {})
            log.debug("Loading extension '{}' using init parameters: '{}".
                      format(ext_name, ext_init_params))
            ext = load_extension(ext_name, ext_init_params)
            bootstrap_chain.append(ext.driver)

        config_frkl = Frkl(frkl_configs, processor_chain=bootstrap_chain)

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

        This will prompt a re-computation of the context the next time it is requested.

        Args:
          configs (list): the configurations, will wrapped in a list if not a list or tuple already
        """

        if not isinstance(configs, (list, tuple)):
            configs = [configs]

        self.configs = list(configs)

        self.context = None

    def append_configs(self, configs):
        """Appends the provided configuration(s) for this Frkl object.

        This will prompt a re-computation of the context the next time it is requested.

        Args:
          configs (list): the configurations, will wrapped in a list if not a list or tuple already
        """

        if not isinstance(configs, (list, tuple)):
            configs = [configs]

        # ensure configs are wrapped
        for c in configs:
            self.configs.append(c)

        self.context = None

    def process(self, result_key='unprocessed'):

        if self.context:
            if result_key == '*':
                return self.context
            else:
                return self.context.get(result_key, None)

        self.context = self.process_configs(self.configs, {})

        if result_key == '*':
            return self.context
        else:
            return self.context.get(result_key, None)

    def process_configs(self, configs, context):
        """Kicks off the processing of the configuration urls.

      Args:
        configs (list): the configs to process

      Returns:
        list: a list of configuration items, corresponding to the input configuration urls
      """

        idx = 0

        configs_copy = copy.deepcopy(configs)
        new_config = configs_copy.pop(0)

        while True:

            log.debug("Processing config: {}".format(new_config))

            if len(configs_copy) > 20:
                raise FrklConfigException("More than 1024 configs, this looks like a loop, exiting.")

            last_processing_result = None
            for current_processor in self.processor_chain:
                result = current_processor.process_config(
                    new_config, copy.deepcopy(context))

                additional_configs = copy.deepcopy(result.more_configs)
                additional_configs.extend(configs_copy)
                configs_copy = additional_configs
                last_processing_result = result.processed_config

                context.setdefault("config_{}".format(idx), {}).setdefault(
                    "history", []).append(last_processing_result)
                if last_processing_result == None:
                    break;

                new_config = last_processing_result

            if last_processing_result != None:
                context.setdefault('unprocessed', []).append(last_processing_result)
                if isinstance(last_processing_result, FrklConfig):
                    last_processing_result = last_processing_result.flatten()
                    context.setdefault('frkl', []).append(last_processing_result)

            idx = idx + 1
            try:
                new_config = configs_copy.pop(0)
            except IndexError:
                break


        context.setdefault('unprocessed', [])
        context.setdefault('frkl', [])
        context['flattened'] = [
            item for sublist in context['frkl'] for item in sublist
        ]

        return context

    def frkl(self):
        """Returns a flattened list of a frklized config chain.

        Returns:
        list: a list of expanded config items
        """

        frkl_list = self.process('frkl')
        return [item for sublist in frkl_list for item in sublist]


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
