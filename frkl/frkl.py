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
import stevedore
import yaml
from jinja2 import BaseLoader, Environment, PackageLoader
from six import string_types

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

STEM_KEY_NAME = "stem_key"
DEFAULT_LEAF_KEY_NAME = "default_leaf_key"
DEFAULT_LEAF_DEFAULT_KEY_NAME = "default_leaf_default_key"
OTHER_VALID_KEYS_NAME = "other_valid_keys"
DEFAULT_LEAF_KEY_MAP_NAME = "default_leaf_key_map"

FRKL_DEFAULT_PARAMS = {
        STEM_KEY_NAME: "childs",
        DEFAULT_LEAF_KEY_NAME: "task",
        DEFAULT_LEAF_DEFAULT_KEY_NAME: "task_name",
        OTHER_VALID_KEYS_NAME: ["vars"],
        DEFAULT_LEAF_KEY_MAP_NAME: "vars"
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

    mgr = stevedore.driver.DriverManager(
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


# ----------------------------------------------------------------
# callbacks
@six.add_metaclass(abc.ABCMeta)
class FrklCallback(object):
    """A class to slurp up configurations from the last element of a processor chain.

    Since those processers might return Generators, it's handy to deal with the results of a config processing
    manually, callbacks seemed like a good way to do it.
    """

    @abc.abstractmethod
    def callback(self, item):
        """Adds a new item to the callback class.

        Args:
          item (object): the newly processed config
        """
        pass

    @abc.abstractmethod
    def result(self):
        """Returns a meaningful representation of all added configs so far.

        Ideally this is a string representation of the (current) state of the callback, since it might
        be used by 3rd party tools for debugging purposes, or as a method to show state in the absence
        of knowledge of the type of FrklCallback that is used.

        Returns:
          object: the current state of the callback
        """
        pass


class MergeResultCallback(FrklCallback):
    """Simple callback, just appends all configs to an internal list."""

    def __init__(self):
        self.result_list = []

    def callback(self, process_result):
        self.result_list.append(process_result)

    def result(self):
        return self.result_list

class ExtendResultCallback(FrklCallback):
    """Simple callback, extends an internal list with the processing results.
    """

    def __init__(self):
        self.result_list = []

    def callback(self, process_result):
        self.result_list.extend(process_result)

    def result(self):
        return self.result_list

class FrklFactoryCallback(FrklCallback):
    """Helper callback method, creates a new Frkl object by processing a list of processor init dicts.
    """

    def __init__(self):
        self.processors = []
        self.bootstrap_chain = []

    def callback(self, item):
        self.processors.append(item)

        ext_name = item.get('processor', {}).get('type', None)
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


# ---------------------------------------------------------------------------
# processors

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
        """Optional method that can be overwritten to process and validate input arguments for this processor.

        Returns:
          bool: whether validation succeeded or not
        """

        return True

    def set_current_config(self, input_config, context):
        """Sets the current configuration.

        Calls the 'new_config' method after assigning the new input configuration to the 'self.current_input_config' variable.

        Args:
          input_config (object): current configuration to be processed
          context (dict): dict that describes the current context / processing state
        """

        self.current_input_config = input_config
        self.current_context = copy.deepcopy(context)

        self.last_call = self.current_context["last_call"]
        self.new_config()

    def new_config(self):
        """Can be overwritten to initially compute a new config after it is first set.

        The newly (last) added input configuration is stored in the 'self.current_input_config' variable.
        """

        pass

    def get_additional_configs(self):
        """Returns additional configs if applicable.

        This is called before the 'process' method.

        Returns:
          list: other configs to be processed next
        """

        return None

    def process(self):
        """Processes the config url or content.

        Calls the 'process_current_config' method internally

        Args:
          input_config (object): input configuration url or content
          last_call (bool): whether this is the 'special' last round of processing

        Returns:
          object: processed config url or content
        """


        if self.last_call:
            if self.current_input_config or self.handles_last_call():
                return self.process_current_config()
            else:
                return None
        else:
            return self.process_current_config()

    def handles_last_call(self):
        """Returns whether this processor wants to be called at the end of a processing run again.

        If the preceiding processer returns a non-None value, this is ignored and the processor is called anyway.

        Returns:
          bool: whether to call this processor for the 'special' last run
        """

        return False

    @abc.abstractmethod
    def process_current_config(self):
        """Processes the config url or content.

        Args:
          input_config (object): input configuration url or content
          last_call (bool): whether this is the 'special' last round of processing

        Returns:
          object: processed config url or content
        """

        pass


class EnsureUrlProcessor(ConfigProcessor):
    """Makes sure the provided string is a url, then downloads the target and reads the content."""

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

    def process_current_config(self):

        result = self.get_config(self.current_input_config)
        return result


class EnsurePythonObjectProcessor(ConfigProcessor):
    """Makes sure the provided string is either valid yaml (or json -- not implemented yet), and converts it into a python object.
  """

    def process_current_config(self):

        config_obj = yaml.load(self.current_input_config)
        return config_obj


class ToYamlProcessor(ConfigProcessor):
    """Takes a python object and returns the string representation.
    """

    def process_current_config(self):

        result = yaml.dump(self.current_input_config, default_flow_style=False)
        return result

class MergeProcessor(ConfigProcessor):
    """Gathers all configs and returns a list of all results as single element."""

    def __init__(self, init_params={}):

        super(MergeProcessor, self).__init__(init_params)
        self.configs = []

    def new_config(self):
        if not self.last_call:
            self.configs.append(self.current_input_config)

    def process_current_config(self):

        if self.last_call:
            return self.configs
        else:
            return None

    def handles_last_call(self):
        return True

class FrklProcessor(ConfigProcessor):
    """A processor to 'expand' python dictionaries using a pre-defined schema.

    This is a bit more complicated to explain than I'd like it to be. For that reason, there is an extra
    page in the docs: link (XXX)
    """

    def __init__(self, init_params={}):

        super(FrklProcessor, self).__init__(init_params)

        self.values_so_far = {}
        self.configs = []

    def validate_init(self):

        self.stem_key = self.init_params[STEM_KEY_NAME]
        self.default_leaf_key = self.init_params[DEFAULT_LEAF_KEY_NAME]
        self.default_leaf_default_key = self.init_params[
            DEFAULT_LEAF_DEFAULT_KEY_NAME]
        self.other_valid_keys = self.init_params[OTHER_VALID_KEYS_NAME]
        self.default_leaf_key_map = self.init_params[DEFAULT_LEAF_KEY_MAP_NAME]
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

    def new_config(self):

        # make sure the new value is a dict, with only allowed keys
        if isinstance(self.current_input_config, (list, tuple)):
            self.configs.extend(self.current_input_config)
        else:
            self.configs.append(self.current_input_config)


    def process_current_config(self):

        result = self.frklize(self.current_input_config, self.values_so_far)

        return result


    def frklize(self, config, current_vars):
        """Recursivly called function which generates (expands) and yields dictionaries matching
        certain criteria (containing leaf_node keys, for example).

        Args:
          config (object): the input config
          current_vars (dict): current state of the (overlayed) var cache
        """

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
        """Processor to replace all occurences of Jinja template strings with values (predefined,
        or potentially dynamically processed in an earlier step).

        Args:
          template_values (dict): a dictionary containing the values to replace template strings with
        """
        self.template_values = template_values

    def process_current_config(self):

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

    def process_current_config(self):

        new_config = self.current_input_config

        for regex, replacement in self.regexes.items():
            new_config = re.sub(regex, replacement, new_config)

        return new_config


class LoadMoreConfigsProcessor(ConfigProcessor):
    """Processort to load additional configs from configs.

    If an incoming configuration is a list of strings, it'll interprete it as list of
    urls and adds it in front of the list of 'yet-to-process' configs of this processing run.

    Use this with caution, since if this gets a list of string that is not a list of urls, it
    will still treat it like one and your run will fail.
    """

    def process_current_config(self):

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

    def process_current_config(self):

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


# simple chain to convert a string (which might be an abbreviated url or path or yaml or json string) into a python object
DEFAULT_PROCESSOR_CHAIN = [
    UrlAbbrevProcessor(), EnsureUrlProcessor(), EnsurePythonObjectProcessor()
]

# format of processor init dicts
BOOTSTRAP_FRKL_FORMAT = {
    STEM_KEY_NAME: "processors",
    DEFAULT_LEAF_KEY_NAME: "processor",
    DEFAULT_LEAF_DEFAULT_KEY_NAME: "type",
    OTHER_VALID_KEYS_NAME: ["init"],
    DEFAULT_LEAF_KEY_MAP_NAME: "init"
}
# chain to bootstrap processor_chain in order to generate a frkl object
BOOTSTRAP_PROCESSOR_CHAIN = [
    UrlAbbrevProcessor(), EnsureUrlProcessor(), EnsurePythonObjectProcessor(),
    FrklProcessor(BOOTSTRAP_FRKL_FORMAT)
]

class Frkl(object):

    def factory(bootstrap_configs, frkl_configs=[]):
        """Factory method to easily create a Frkl object using a list of configurations to describe
        the format of the configs to use later on, as well as (optionally) a list of such configs.

        Args:
          bootstrap_configs (list): the configuration to describe the format of the configurations the new Frkl object uses
          frkl_configs (list): (optional) configurations to init the Frkl object with. this can also be done later using the 'set_configs' method

        Returns:
          Frkl: a new Frkl object
        """

        if isinstance(bootstrap_configs, string_types):
            bootstrap_configs = [bootstrap_configs]

        bootstrap = Frkl(bootstrap_configs, BOOTSTRAP_PROCESSOR_CHAIN)
        config_frkl = bootstrap.process(FrklFactoryCallback())

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
        """Kicks off the processing of the configuration urls.

      Args:
        callback (FrklCallback): callback to use for this processing run, defaults to 'MergeResultCallback'

      Returns:
        object: the value of the result() method of the callback
      """

        if not callback:
            callback = MergeResultCallback()

        idx = 0

        configs_copy = copy.deepcopy(self.configs)
        context = {}
        context["last_call"] = False

        while configs_copy:

            if len(configs_copy) > 1024:
                raise FrklConfigException("More than 1024 configs, this looks like a loop, exiting.")

            config = configs_copy.pop(0)
            context["current_original_config"] = config

            self.process_single_config(config, self.processor_chain, callback, configs_copy, context)

        current_config = None
        context["next_configs"] = []

        for idx, prc in enumerate(self.processor_chain):
            context["current_config"] = current_config
            context["last_call"] = True
            context["current_processor_chain"] = self.processor_chain[idx:]
            context["current_processor"] = prc
            prc.set_current_config(current_config, context)
            current_config = prc.process()

        if current_config:
            callback.callback(current_config)

        return callback.result()

    def process_single_config(self, config, processor_chain, callback, configs_copy, context):
        """Helper method to be able to recursively call the next processor in the chain.

        Args:
          config (object): the current config object
          processor_chain (list): the list of processor items to use (reduces by one with every recursive run)
          callback (FrklCallback): the callback that receives any potential results
          configs_copy (list): list of configs that still need processing, this method might prepend newly processed configs to this
          context (dict): context object, can be used by processors to investigate current state, history, etc.
        """

        if not config:
            return

        if not processor_chain:
            callback.callback(config)
            return

        current_processor = processor_chain[0]
        temp_config = copy.deepcopy(config)

        context["current_processor"] = current_processor
        context["current_config"] = temp_config
        context["current_processor_chain"] = processor_chain
        context["next_configs"] = configs_copy

        current_processor.set_current_config(temp_config, context)

        additional_configs = current_processor.get_additional_configs()
        if additional_configs:
            configs_copy[0:0] = additional_configs

        last_processing_result = current_processor.process()
        if isinstance(last_processing_result, types.GeneratorType):
            for item in last_processing_result:
                self.process_single_config(item, processor_chain[1:], callback, configs_copy, context)

        else:
            self.process_single_config(last_processing_result, processor_chain[1:], callback, configs_copy, context)
