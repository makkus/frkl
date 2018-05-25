# -*- coding: utf-8 -*-

# python 3 compatibility
from __future__ import absolute_import, division, print_function, unicode_literals

from .chains import *
from .processors import *

# import yaml

try:
    set
except NameError:
    # noinspection PyDeprecation,PyCompatibility
    from sets import Set as set

try:
    # noinspection PyCompatibility
    from urllib.request import urlopen

    # noinspection PyCompatibility
    from urllib.parse import urlparse
except ImportError:
    # noinspection PyCompatibility
    from urlparse import urlparse
    from urllib import urlopen

__metaclass__ = type

log = logging.getLogger("frkl")


class Frkl(object):

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
            from .callbacks import MergeResultCallback

            callback = MergeResultCallback()

        idx = 0

        configs_copy = copy.deepcopy(self.configs)
        context = {"last_call": False}

        callback.started()

        while configs_copy:

            if len(configs_copy) > 1024:
                raise FrklConfigException(
                    "More than 1024 configs, this looks like a loop, exiting."
                )

            config = configs_copy.pop(0)
            context["current_original_config"] = config

            self.process_single_config(
                config, self.processor_chain, callback, configs_copy, context
            )

        current_config = None
        context["next_configs"] = []

        context["current_config"] = current_config
        context["last_call"] = True
        self.process_single_config(
            current_config, self.processor_chain, callback, [], context
        )

        callback.finished()

        return callback.result()

    def process_single_config(
        self, config, processor_chain, callback, configs_copy, context
    ):
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
                self.process_single_config(
                    item, processor_chain[1:], callback, configs_copy, context
                )

        else:
            self.process_single_config(
                last_processing_result,
                processor_chain[1:],
                callback,
                configs_copy,
                context,
            )
