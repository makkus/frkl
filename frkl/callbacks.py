# -*- coding: utf-8 -*-

# python 3 compatibility
from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

from .processors import *

# import yaml
from .chains import *
from .frkl import Frkl


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

def load_collector(name, init_params=None):
    """Loading a collector extension.

    Args:
      name (str): the registered name of the collector
      init_params (dict): the parameters to initialize the extension object

    Returns:
      FrklCallback: the extension collector
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
        namespace='frkl.collector',
        name=name,
        invoke_on_load=True,
        invoke_args=(init_params, ))
    log.debug("Registered plugins: {}".format(", ".join(
        ext.name for ext in mgr.extensions)))

    return mgr

# ----------------------------------------------------------------
# callbacks / collectors
@six.add_metaclass(abc.ABCMeta)
class FrklCallback(object):
    """A class to slurp up configurations from the last element of a processor chain.

    Since those processers might return Generators, it's handy to deal with the results of a config processing
    manually, callbacks seemed like a good way to do it.
    """

    def init(init_file, configs):
        """Creates a collector object with associated Frkl and processor chain.

        The init file needs to be yaml, with the 'collector' key being a registered collector plugin,
        and the 'processor_chain' key being a list of registered ConfigProcessor objects.

        Args:
          init_file: the path to the init file
          configs: the configuration item(s) for this processor
        Returns:
          FrklCallback: the collector item
        """

        yaml = YAML(typ='safe')

        with open(init_file) as f:
            init_config = yaml.load(f)
            #content = f.read()


        #init_config = yaml.safe_load(content)

        if isinstance(init_config, (list, tuple)):
            processor_chain = init_config
            collector_name = "default"
        elif not isinstance(init_config, dict):
            raise Exception(
                "init configuration needs to be either list of processor configs, or dict with 'processor_chain' and optionally 'collector' keys"
            )
        else:
            if "processor_chain" not in init_config.keys():
                raise Exception(
                    "No processor chain specified in '{}'".format(init_file))

            processor_chain = init_config["processor_chain"]
            if not processor_chain:
                raise Exception(
                    "Processor chain in '{}' empty".format(init_file))

            if "collector" not in init_config.keys():
                collector_name = "default"
            else:
                collector_name = init_config["collector"]

        if isinstance(collector_name, string_types):
            collector_init = {}
        elif not isinstance(collector_name, dict) or len(collector_name) != 1:
            raise Exception(
                "'collector' value needs to be either a string or a dict with length 1"
            )
        else:
            temp = collector_name
            collector_name = list(temp.keys())[0]
            collector_init = temp[collector_name]

        if collector_name == 'default':
            collector_name = 'merge'

        collector = load_collector(collector_name, collector_init).driver
        bootstrap = Frkl(processor_chain,
                         COLLECTOR_INIT_BOOTSTRAP_PROCESSOR_CHAIN)
        config_frkl = bootstrap.process(FrklFactoryCallback())

        config_frkl.set_configs(configs)

        temp = config_frkl.process(collector)
        return collector

    init = staticmethod(init)

    def __init__(self, init_params=None):

        if init_params is None:
            init_params = {}
        self.init_params = init_params

        msg = self.validate_init()
        if msg is not True:
            raise FrklConfigException(msg)

    def validate_init(self):
        """Optional method that can be overwritten to process and validate input arguments for this processor.

        Returns:
          bool: whether validation succeeded or not
        """

        return True

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

    def started(self):
        """Optional method that can be overwritten if the callback needs to know when the processing has started."""

        pass

    def finished(self):
        """Optional method that can be overwritten if the callback needs to know when the processing has finished."""

        pass


class MergeDictResultCallback(FrklCallback):
    """Simple callback, merges all configs to *one* internal dict."""

    def __init__(self, init_params=None):
        super(MergeDictResultCallback, self).__init__(init_params)
        self.result_dict = {}
        self.append_keys_map = {}

    def validate_init(self):
        """Optional method that can be overwritten to process and validate input arguments for this processor.

        Returns:
          bool: whether validation succeeded or not
        """

        self.append_keys = self.init_params.get("append_keys", [])
        if not isinstance(self.append_keys, (list, tuple)):
            self.append_keys = [self.append_keys]

        return True

    def get_dict_detail(self, target_dict, detail_path):

        if not target_dict:
            return default_value
        temp = target_dict
        for level in detail_path.split("/"):
            temp = temp.get(level, {})

        return temp

    def set_dict_detail(self, target_dict, detail_path, new_value):

        temp = target_dict
        tokens = detail_path.split("/")
        for level in tokens[0:-1]:
            if level not in temp.keys():
                temp[level] = {}
            temp = temp[level]

        temp[tokens[-1]] = new_value

    def callback(self, process_result):

        for ak in self.append_keys:
            v = self.get_dict_detail(process_result, ak)
            if v:
                if not isinstance(v, (list, tuple)):
                    v = [v]
                self.append_keys_map.setdefault(ak, []).extend(v)

        dict_merge(self.result_dict, process_result, copy_dct=False)

    def result(self):

        for k, v in self.append_keys_map.items():
            self.set_dict_detail(self.result_dict, k, v)

        return self.result_dict


class MergeResultCallback(FrklCallback):
    """Simple callback, just appends all configs to an internal list."""

    def __init__(self, init_params=None):
        super(MergeResultCallback, self).__init__(init_params)

        self.result_list = []

    def callback(self, process_result):
        self.result_list.append(process_result)

    def result(self):
        return self.result_list


class ExtendResultCallback(FrklCallback):
    """Simple callback, extends an internal list with the processing results.
    """

    def __init__(self, init_params=None):
        super(ExtendResultCallback, self).__init__(init_params)
        self.result_list = []

    def callback(self, process_result):
        self.result_list.extend(process_result)

    def result(self):
        return self.result_list


class FrklFactoryCallback(FrklCallback):
    """Helper callback method, creates a new Frkl object by processing a list of processor init dicts.
    """

    def __init__(self, init_params=None):
        super(FrklFactoryCallback, self).__init__(init_params)
        self.processors = []
        self.bootstrap_chain = []

    def callback(self, item):
        self.processors.append(item)

        ext_name = item.get('processor', {}).get('type', None)
        if not ext_name:
            raise FrklConfigException(
                "Can't parse processor name using config: {}".format(item))
        ext_init_params = item.get('init', {})
        log.debug("Loading extension '{}' using init parameters: '{}".format(
            ext_name, ext_init_params))
        ext = load_extension(ext_name, ext_init_params)
        self.bootstrap_chain.append(ext.driver)

    def result(self):
        return Frkl([], self.bootstrap_chain)

