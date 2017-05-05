# -*- coding: utf-8 -*-

# python 3 compatibility
from __future__ import absolute_import, division, print_function, unicode_literals

__metaclass__ = type

log = logging.getLogger("freckles")

DEFAULT_ABBREVIATIONS = {
    'gh': ["https://raw.githubusercontent.com", -1, -1, "master"]
}


class Frkl(object):

    """Base object to hold the configuration itself."""
