# -*- coding: utf-8 -*-

# python 3 compatibility
from __future__ import absolute_import, division, print_function, unicode_literals

import os
from six import string_types

from frkl import Frkl
from frutils import calculate_cache_location_for_url, ensure_parent_dir
from frutils.defaults import JINJA_DELIMITER_PROFILES, DEFAULT_DOWNLOAD_CACHE_BASE
from ruamel.yaml import YAML

from .defaults import *
from .processors import (
    EnsurePythonObjectProcessor,
    EnsureUrlProcessor,
    FrklProcessor,
    UrlAbbrevProcessor,
    Jinja2TemplateProcessor
)

def get_full_url(abbrev_or_url, abbrevs=None):
    """Expands input to a full url if abbreviated.

    Args:
        abbrev_or_url (str): a full or abbreviated url

    Returns
        str: the full url
    """

    u = UrlAbbrevProcessor(abbrevs=abbrevs)
    chain = [u]

    single_input = False
    if isinstance(abbrev_or_url, string_types):
        single_input = True
        urls = [abbrev_or_url]

    f = Frkl(urls, chain)
    result = f.process()

    if single_input:
        if not result:
            return []
        return result[0]
    else:
        return result


def download_cached_file(abbrev_or_url, update=False, cache_base=DEFAULT_DOWNLOAD_CACHE_BASE, abbrevs=None, return_content=False):
    """Downloads a file using a full or abbreviated url.

    Args:
        abbrev_or_url (str): the full or abbreviated url
        update (bool): whether to 'force' update the file if it doesn't exist
        cache_base (str): root of cache directory
        abbrevs (dict): (optional) url abbreviations
        return_content (bool): whether to return the path to the file (False) or it's content (True)

    Returns:
        str: the path to the downloaded file or it's content (depending on the 'return_content' variable)
    """

    if not isinstance(abbrev_or_url, string_types):
        raise Exception("Url needs to be string")

    rel_cache_path = calculate_cache_location_for_url(get_full_url(abbrev_or_url))

    target_file = os.path.realpath(os.path.join(cache_base, rel_cache_path))
    if os.path.exists(target_file) and os.path.isfile(target_file) and not update:
        if return_content:
            with open(target_file) as f:
                content = f.read()
                return content
        else:
            return target_file
    elif os.path.exists(target_file) and not os.path.isfile(target_file):
        raise Exception("Target file is not a file: {}".format(target_file))

    chain = [UrlAbbrevProcessor(abbrevs=abbrevs), EnsureUrlProcessor()]

    f = Frkl([abbrev_or_url], chain)
    result = f.process()[0]

    ensure_parent_dir(target_file)
    with open(target_file, 'w') as f:
        f.write(result)

    if return_content:
        return result
    else:
        return target_file


def content_from_url(abbrev_or_url, update=False, cache_base=DEFAULT_DOWNLOAD_CACHE_BASE, abbrevs=None):
    """Downloads a file using a full or abbreviated url and returns it's content.

    Args:
        abbrev_or_url (str): the full or abbreviated url
        update (bool): whether to 'force' update the file if it doesn't exist
        cache_base (str): root of cache directory
        abbrevs (dict): (optional) url abbreviations

    Returns:
        str: the content of the downloaded file
    """

    content = download_cached_file(abbrev_or_url, update=update, cache_base=cache_base, abbrevs=abbrevs, return_content=True)
    return content

def dict_from_url(abbrev_or_url, update=False, cache_base=DEFAULT_DOWNLOAD_CACHE_BASE, abbrevs=None):
    """Downloads a file using a full or abbreviated url and returns it's content as a python dict.

    Args:
        abbrev_or_url (str): the full or abbreviated url
        update (bool): whether to 'force' update the file if it doesn't exist
        cache_base (str): root of cache directory
        abbrevs (dict): (optional) url abbreviations

    Returns:
        str: the content of the downloaded file
    """

    content = download_cached_file(abbrev_or_url, update=update, cache_base=cache_base, abbrevs=abbrevs, return_content=True)
    yaml = YAML(typ="safe")

    result = yaml.load(content)
    return result




