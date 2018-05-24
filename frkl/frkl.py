# -*- coding: utf-8 -*-

# python 3 compatibility
from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import abc
import collections
import copy
import logging
import os
import re
import sys
import types

import requests
import six
import stevedore
#import yaml
from builtins import *
from jinja2 import BaseLoader, Environment
from six import string_types

from .defaults import *
from .callbacks import *
from .processors import *

try:
    set
except NameError:
    # noinspection PyDeprecation
    from sets import Set as set

try:
    from urllib.request import urlopen
    from urllib.parse import urlparse
except ImportError:
    from urlparse import urlparse
    from urllib import urlopen

__metaclass__ = type

log = logging.getLogger("frkl")



class Frkl(object):
    def init(files_or_folders,
             additional_configs=None,
             use_strings_as_config=False):
        """Creates a Frkl object.

        Args:
          files_or_folders (list): a list of files or folders or url strings. if the item is a file or url string, it will be used as Frkl bootstrap config, if it is a folder, it is forwarded to the 'from_folder' method to get lists of bootstrap and/or config files
          additional_configs (list): a list of files or url strings, used as configs for the initialized Frlk object
          use_strings_as_config (bool): whether to use non-folder strings as config files (instead of to initialze the Frkl object, which is default)

        Returns:
          Frkl: the object
        """

        if additional_configs is None:
            additional_configs = []
        chain_files = []
        config_files = []

        for f in files_or_folders:
            if not os.path.exists(f):
                # means this is a url string
                if not use_strings_as_config:
                    chain_files.append(f)
                else:
                    config_files.append(f)
            elif os.path.isfile(f):
                # means we can use this directly
                chain_files.append(f)
            else:
                temp_chain, temp_config = Frkl.get_configs(f)
                chain_files.extend(temp_chain)
                config_files.extend(temp_config)

        if not chain_files:
            raise FrklConfigException(
                "No bootstrap information for Frkl found, can't create object."
            )

        frkl_obj = Frkl.factory(chain_files, config_files)
        return frkl_obj

    init = staticmethod(init)

    def from_folder(folders):
        """Creates a Frkl object using a folder path as the only input.

        The folder needs to contain one or more files that start with the '_' and end with '.yml',
        which are used to bootstrap the frkl object by reading them in alphabetical order,
        and one or more additional files with the 'yml' extension, which are then used as
        input configurations, again in alphabetical order.

        Args:
          folders (list): paths to local folder(s)

        Returns:
          Frkl: the initialized Frkl object
        """

        chain_files, config_files = Frkl.get_configs(folders)

        if not chain_files:
            raise FrklConfigException(
                "No bootstrap information for Frkl found, can't create object."
            )

        frkl_obj = Frkl.factory(chain_files, config_files)
        return frkl_obj

    from_folder = staticmethod(from_folder)

    def get_configs(folders):
        """Looks at a folder and retrieves configs.

        The folders need to contain one or more files that start with the '_' and end with '.yml',
        which are used to bootstrap the frkl object by reading them in alphabetical order,
        and one or more additional files with the 'yml' extension, which are then used as
        input configurations, again in alphabetical order.

        Args:
          folders (list): paths to one or several local folders

        Returns:
          tuple: first element of the tuple is a list of bootstrap configurations, 2nd element is a list of actual configs
        """

        if isinstance(folders, string_types):
            folders = [folders]

        all_chains = []
        all_configs = []
        for folder in folders:
            chain_files = []
            config_files = []
            for child in os.listdir(folder):
                if not child.startswith("__") and child.startswith(
                        "_") and child.endswith(".yml"):
                    chain_files.append(os.path.join(folder, child))
                elif child.endswith(".yml"):
                    config_files.append(os.path.join(folder, child))

            chain_files.sort()
            config_files.sort()

            all_chains.extend(chain_files)
            all_configs.extend(config_files)

        return (all_chains, all_configs)

    get_configs = staticmethod(get_configs)

    def factory(bootstrap_configs, frkl_configs=None):
        """Factory method to easily create a Frkl object using a list of configurations to describe
        the format of the configs to use later on, as well as (optionally) a list of such configs.

        Args:
          bootstrap_configs (list): the configuration to describe the format of the configurations the new Frkl object uses
          frkl_configs (list): (optional) configurations to init the Frkl object with. this can also be done later using the 'set_configs' method

        Returns:
          Frkl: a new Frkl object
        """

        if frkl_configs is None:
            frkl_configs = []
        if isinstance(bootstrap_configs, string_types):
            bootstrap_configs = [bootstrap_configs]

        bootstrap = Frkl(bootstrap_configs, BOOTSTRAP_PROCESSOR_CHAIN)
        config_frkl = bootstrap.process(FrklFactoryCallback())

        config_frkl.set_configs(frkl_configs)
        return config_frkl

    factory = staticmethod(factory)

    def __init__(self, configs=None, processor_chain=DEFAULT_PROCESSOR_CHAIN):
        """Base object that holds the configuration.

        Args:
          configs (list): list of configurations, will be processed in the order they come in
          processor_chain (list): processor chain to use, defaults to [:class:`UrlAbbrevProcessor`]
L        """

        if configs is None:
            configs = []
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
        context = {"last_call": False}

        callback.started()

        while configs_copy:

            if len(configs_copy) > 1024:
                raise FrklConfigException(
                    "More than 1024 configs, this looks like a loop, exiting.")

            config = configs_copy.pop(0)
            context["current_original_config"] = config

            self.process_single_config(config, self.processor_chain, callback,
                                       configs_copy, context)

        current_config = None
        context["next_configs"] = []

        context["current_config"] = current_config
        context["last_call"] = True
        self.process_single_config(current_config, self.processor_chain,
                                   callback, [], context)

        callback.finished()

        return callback.result()

    def process_single_config(self, config, processor_chain, callback,
                              configs_copy, context):
        """Helper method to be able to recursively call the next processor in the chain.

        Args:
          config (object): the current config object
          processor_chain (list): the list of processor items to use (reduces by one with every recursive run)
          callback (FrklCallback): the callback that receives any potential results
          configs_copy (list): list of configs that still need processing, this method might prepend newly processed configs to this
          context (dict): context object, can be used by processors to investigate current state, history, etc.
        """

        if not context.get("last_call", False):
            if not config:
                return

        if not processor_chain:
            if config:
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
                self.process_single_config(item, processor_chain[1:], callback,
                                           configs_copy, context)

        else:
            self.process_single_config(last_processing_result,
                                       processor_chain[1:], callback,
                                       configs_copy, context)
