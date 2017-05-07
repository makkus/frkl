# -*- coding: utf-8 -*-

# python 3 compatibility
from __future__ import absolute_import, division, print_function, unicode_literals

import contextlib
import copy
import logging
import pprint
import re
import os
import requests

try:
  from urllib.request import urlopen
  from urllib.parse import urlparse
except ImportError:
  from urlparse import urlparse
  from urllib import urlopen

__metaclass__ = type

log = logging.getLogger("frkl")

PLACEHOLDER = -9876

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
            dict_merge(dct[k], merge_dct[k])
        else:
            dct[k] = merge_dct[k]

    return dct

CONFIG_PROCESSOR_VALUE_TYPES = ["STRING", "URL", "JSON", "YAML", "DICT"]

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

        if isinstance(config_file_url, dict):
            raise Exception("XXX")

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
                content = r.text
            except:
                raise Exception("XXX")

        else:
            raise Exception("XXX")

        return content

    def process(self, input_config):

        result = self.get_config(input_config)
        return result


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


DEFAULT_PROCESSOR_CHAIN = [UrlAbbrevProcessor()]

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
