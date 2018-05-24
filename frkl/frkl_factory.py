# -*- coding: utf-8 -*-

# python 3 compatibility
from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

from .callbacks import *
from .processors import *
from .chains import *

from .frkl import Frkl
# import yaml

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

