# -*- coding: utf-8 -*-

import logging

from six import string_types

from .frkl import Frkl
from .processors import UrlAbbrevProcessor

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
