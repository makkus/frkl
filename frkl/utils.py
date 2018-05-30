# -*- coding: utf-8 -*-

import logging

from six import string_types

from frutils.defaults import *
from .frkl import Frkl
from .processors import UrlAbbrevProcessor, EnsureUrlProcessor, ParentPathProcessor
from .callbacks import SetResultCallback

log = logging.getLogger("frkl")


def expand_string_to_git_details(value, default_abbrevs):

    fail_msg = None
    branch = None
    opt_split_string = "::"
    if opt_split_string in value:
        tokens = value.split(opt_split_string)
        opt = tokens[1:-1]
        if not opt:
            raise Exception(
                "Not a valid url, needs at least 2 split strings ('{}')".format(
                    opt_split_string
                )
            )
        if len(opt) != 1:
            raise Exception("Not a valid url, can only have 1 branch: {}".format(value))
        branch = opt[0]

    result = expand_string_to_git_repo(value, default_abbrevs)

    result = {"url": result}

    if branch:
        result["branch"] = branch

    return result


def expand_string_to_git_repo(value, default_abbrevs):
    if isinstance(value, string_types):
        is_string = True
    elif isinstance(value, (list, tuple)):
        is_string = False
    else:
        raise Exception(
            "Not a supported type (only string or list are accepted): {}".format(value)
        )

    try:
        frkl_obj = Frkl(
            value,
            [
                UrlAbbrevProcessor(
                    init_params={
                        "abbrevs": default_abbrevs,
                        "add_default_abbrevs": False,
                    }
                )
            ],
        )
        result = frkl_obj.process()
        if is_string:
            return result[0]
        else:
            return result
    except (Exception) as e:
        raise Exception("'{}' is not a valid repo url: {}".format(value, e))


def get_url_parents(urls, abbrevs=False, return_list=False):
    """Helper methods to calculate the parents of the provided urls.

    Args:
        urls (list): the list of urls
        abbrevs (bool, dict): if False, urls won't be expanded if they are abbreviated, otherwise if a abbrev dict is provided, they will be
        return_list (bool): whether to return the result as set (False) or list (True)
    """

    if abbrevs is False or abbrevs is None:
        chain = [ParentPathProcessor()]
    else:
        if abbrevs is True:
            abbrevs = DEFAULT_URL_ABBREVIATIONS_FILE
        chain = [
            UrlAbbrevProcessor(
                init_params={"abbrevs": abbrevs, "add_default_abbrevs": False}
            ),
            ParentPathProcessor(),
        ]
    callback = SetResultCallback(init_params={"return_list": return_list})

    frkl_obj = Frkl(urls, chain)
    result = frkl_obj.process(callback)

    return result
