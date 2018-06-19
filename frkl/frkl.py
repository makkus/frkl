# -*- coding: utf-8 -*-

# python 3 compatibility
from __future__ import absolute_import, division, print_function, unicode_literals

from .chains import *
from .processors import *

__metaclass__ = type

log = logging.getLogger("frkl")


class Frkl(object):

    def __init__(
        self, configs=None, processor_chain=LOAD_OBJECT_FROM_URL_CHAIN, max_items=9999
    ):
        """Base object that holds the configuration.

        Args:
          configs (list): list of configurations, will be processed in the order they come in
          processor_chain (list): processor chain to use, defaults to [:class:`UrlAbbrevProcessor`]
          max_items (int): max number of items to allow, mostly used to catch bugs in the code, contact the developer if you hit this number
L        """

        if configs is None:
            configs = []
        if not isinstance(processor_chain, (list, tuple)):
            processor_chain = [processor_chain]
        self.processor_chain = processor_chain

        self.configs = []
        self.set_configs(configs)
        self.max_items = max_items

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

        configs_copy = copy.deepcopy(self.configs)
        context = {"last_call": False}

        callback.started()

        while configs_copy:

            if len(configs_copy) > self.max_items:
                raise FrklConfigException(
                    "More than {} configs, this looks like a loop, exiting. Contact the developer to up that limit if you think this is an issue.".format(
                        self.max_items
                    )
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


# several useful or common helper methods


def load_object_from_url_or_path(urls):
    """Simple wrapper to create a list of dictionaries from a local or remote file.

    If input is a single url, a single list will be returned. If a list,
    the result will be a list of lists.

    As this uses safe_load with the yaml parser, the dictionary will probably not be in the same order as in the original file.

    Args:
        urls (list): a list of paths and/or urls
        safe_load (bool): whether to use safe load with the yaml parser. This will destroy the order of a dict.
    Returns:
        list: a list of dictionaries, representing the content of the input files
    """

    single_input = False
    if isinstance(urls, string_types):
        single_input = True
        urls = [urls]

    f = Frkl(urls, LOAD_OBJECT_FROM_URL_CHAIN)
    result = f.process()

    if single_input:
        return result[0]
    else:
        return result


def load_string_from_url_or_path(
    urls,
    template_vars=None,
    delimiter_profile=JINJA_DELIMITER_PROFILES["default"],
    use_environment_vars=False,
    use_context=False,
    create_python_object=False,
    safe_load=True,
):
    """Simple wrapper to create a list of dictionaries from a local or remote file.

    If input is a single url, a single list will be returned. If a list,
    the result will be a list of lists.

    Args:
        urls (list): a list of paths and/or urls
        template_vars (dict): if not None, the string will be considered a jinja2 template and this dict will be used as replacemnt dict
        delimiter_profile (dict): the delimiter profile, if templating
        use_environment_vars (bool, str): whether to also use environment variables when templating
        use_context (bool, str): whether to also use the frkl context when templating
        create_python_object (bool): whether to create a python object out of the result string or not
    Returns:
        list: a string or python object, representing the content of the input files
    """

    single_input = False
    if isinstance(urls, string_types):
        single_input = True
        urls = [urls]

    chain = load_templated_string_from_url_chain(
        template_vars,
        create_python_object=create_python_object,
        use_environment_vars=use_environment_vars,
        use_context=use_context,
        delimiter_profile=delimiter_profile,
    )

    f = Frkl(urls, chain)
    result = f.process()

    if single_input:
        if not result:
            return []
        return result[0]
    else:
        return result
