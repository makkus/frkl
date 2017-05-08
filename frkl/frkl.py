# -*- coding: utf-8 -*-

# python 3 compatibility
from __future__ import absolute_import, division, print_function, unicode_literals

from sets import Set
import contextlib
import copy
import logging
import pprint
import re
import os
import requests
from jinja2 import BaseLoader, Environment, PackageLoader
import yaml
from six import string_types

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

DEFAULT_ABBREVIATIONS = {
    'gh': ["https://raw.githubusercontent.com", PLACEHOLDER, PLACEHOLDER, "master"],
    'bb': ["https://bitbucket.org", PLACEHOLDER, PLACEHOLDER, "src", "master"]
}


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
        if (k in dct and isinstance(dct[k], dict)
                and isinstance(merge_dct[k], collections.Mapping)):
            dict_merge(dct[k], merge_dct[k], copy_dct=False)
        else:
            dct[k] = merge_dct[k]

    return dct

CONFIG_PROCESSOR_VALUE_TYPES = ["STRING", "URL", "JSON", "YAML", "DICT"]

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

# ------------------------------------------------------------------------
# Processing configuration(s)

class ConfigProcessor(object):
    """Abstract base class for config url/content manipulators.

    In order to enable configuration urls and content to be written as quickly and minimal as possible, frkl supports pluggable processors that can manipulate the configuration urls and contents. For example, urls can be appbreviated 'gh' -> 'https://raw.githubusercontent.com/blahblah'.
    """

    def get_supported_input_value_type():
        return "STRING"

    def get_supported_output_value_type():
        return "STRING"

    def process(self, input_config):
        """Processes the config url or content.

        Args:
          input_config (str): input configuration url or content

        Returns:
          str: processed config url or content
        """

        return None

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
            except Exception, e:
                raise FrklConfigException("Could not retrieve configuration from: {}".format(config_file_url), e)
        else:
            raise FrklConfigException("Not a supported config file url or no local file found: {}".format(config_file_url))

        return content

    def process(self, input_config):

        result = self.get_config(input_config)
        return result

class EnsurePythonObjectProcessor(ConfigProcessor):
  """Makes sure the provided string is either valid yaml or json, and converts it into a str.
  """

  def process(self, input_config):

    config_dict = yaml.load(input_config)
    return config_dict

class FrklConfig(object):

  def __init__(self, config):
    self.config = copy.deepcopy(config)

  def flatten(self):

    result_dict = {}
    for var, value_dicts in self.config.items():
      result_dict[var] = {}
      for value_dict in value_dicts:
        dict_merge(result_dict[var], value_dict, copy_dct=False)

    return result_dict
  
class FrklConfigs(object):

  def __init__(self):
    self.configs = []

  def append(self, config):
    self.configs.append(config)

  def flatten(self):
    return [conf.flatten() for conf in self.configs]

class FrklDictProcessor(ConfigProcessor):
  """Expands an elastic dict.
  """

  def __init__(self, stem_key, default_leaf_key, default_leaf_default_key, other_valid_keys=[], default_leaf_key_map={}):

    self.stem_key = stem_key
    self.default_leaf_key = default_leaf_key
    self.default_leaf_default_key = default_leaf_default_key
    self.other_valid_keys = other_valid_keys
    if isinstance(default_leaf_key_map, string_types):
      self.default_leaf_key_map = { "*": default_leaf_key_map }
    elif isinstance(default_leaf_key_map, dict):
      self.default_leaf_key_map = default_leaf_key_map
    else:
      raise FrklConfigException("Type '{}' not supported for default leaf key map.".format(type(default_leaf_key_map)))

    self.all_keys = Set([self.stem_key, self.default_leaf_key])
    self.all_keys.update(self.other_valid_keys)

  def process(self, input_config):
    root = FrklConfigs()
    self.frklize(input_config, root=root)
    return root

  def frklize(self, new_value,  root=[], values_so_far_parent={}):

    values_so_far = copy.deepcopy(values_so_far_parent)

    # mkaing sure the new value is a dict, with only allowed keys
    if isinstance(new_value, string_types):
      new_value = {self.default_leaf_key: {self.default_leaf_default_key: new_value}}
    elif isinstance(new_value, (list, tuple)):
      for item in new_value:
        self.frklize(item, root, values_so_far)
      return

    if not isinstance(new_value, dict):
      raise FrklConfigException("Not a supported type for value '{}': {}".format(new_value, type(new_value)))

    # we check whether any of the known keys is available here, if not,
    # we check whether there is a default key registered for the name (single) key
    if not any(x in new_value.keys() for x in self.all_keys):
      # if there are more than one keys in this, it's difficult to figure out what to do here, so for now let's just not allow that
      if len(new_value.keys()) != 1:
        raise FrklConfigException("If not using the full config format, leaf nodes are only allowed to have one key: {}".format(new_value))

      # the string value of the key, this will be end up as the default_leaf_default_key of the default_leaf_key
      key = new_value.keys()[0]

      # we need to know where to put the value of this, if it's not registered beforehand we raise an exception
      if not isinstance(new_value[key], dict) or not any(x in new_value[key].keys() for x in self.all_keys):
        if not key in self.default_leaf_key_map.keys() and not '*' in self.default_leaf_key_map.keys():
          raise FrklConfigException("Can't find registered default key and value for shortcut value: {}".format(key))

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
        dict_merge(temp_new_value, {self.default_leaf_key: {self.default_leaf_default_key: key}}, copy_dct=False)
        new_value = temp_new_value
      # else we put the whole dict under the default_leaf_key
      else:
        temp_new_value = {self.default_leaf_key: {self.default_leaf_default_key: key}}
        dict_merge(temp_new_value, {self.default_leaf_default_key: new_value[key]}, copy_dct=False)
        new_value = temp_new_value

    if self.stem_key in new_value.keys() and self.default_leaf_key in new_value.keys():
      raise FrklConfigException("Configuration can't have both stem key ({}) and default leaf key ({}) on the same level: {}".format(self.stem_key, self.default_leaf_key, new_value))

    stem = new_value.pop(self.stem_key, NO_STEM_INDICATOR)

    temp = {}
    dict_merge(temp, values_so_far, copy_dct=False)
    dict_merge(temp, new_value, copy_dct=False)
    new_value = temp

    for key in new_value.keys():
      if key not in self.all_keys:
        raise FrklConfigException("Key '{}' not allowed (in {})".format(key, new_value))

      values_so_far.setdefault(key, []).append(new_value[key])

    if stem == NO_STEM_INDICATOR:
      if self.default_leaf_key in new_value:
        root.append(FrklConfig(values_so_far))
      return
    elif isinstance(stem, (list, tuple)) and not isinstance(stem, string_types):
      self.frklize(stem, root, values_so_far)
    else:
      raise FrklConfigException("Value of {} must be list (is: '{}')".format(self.stem_key, type(stem)))

class Jinja2TemplateProcessor(ConfigProcessor):

    def __init__(self, template_values={}):
        self.template_values = template_values

    def process(self, input_config):

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
        return self.expand_config(input_config)

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

            if isinstance(self.abbrevs[prefix], basestring):
                return "{}{}".format(self.abbrevs[prefix], rest)
            else:
                tokens = rest.split("/")
                result_string = ""
                for t in self.abbrevs[prefix]:

                    if t == PLACEHOLDER:
                        if not tokens:
                            raise FrecklesConfigError("Can't expand url '{}': not enough parts.", 'config', url)
                        to_append = tokens.pop(0)
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


def process_chain(configs, processor_chain):
    """Processes the given input using the proviced chain of processors.
    """

    result = []

    for c in configs:
        new_config = c

        for p in processor_chain:
            new_config = p.process(new_config)
        result.append(new_config)

    return result

DEFAULT_PROCESSOR_CHAIN = [UrlAbbrevProcessor()]
# ----------------------------------------------------------------

class Frkl(object):

    def __init__(self, configs, stem_key="config", other_valid_keys=[], processor_chain=DEFAULT_PROCESSOR_CHAIN):
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

        self.orig_configs = configs
        self.stem_key = stem_key
        self.other_valid_keys = other_valid_keys
        self.processor_chain = processor_chain

        self.configs = process_chain(self.orig_configs, self.processor_chain)



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
