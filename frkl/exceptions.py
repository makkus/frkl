# -*- coding: utf-8 -*-

# python 3 compatibility
from __future__ import absolute_import, division, print_function, unicode_literals


# ------------------------------------------------------------------------
# Frkl Exception(s)


class FrklConfigException(Exception):

    def __init__(self, message, errors=None):
        """Exception that is thrown when processing configuration urls/content.

        Args:
          message (str): the error message
          errors (list): list of root causes and error descriptions
        """

        super(FrklConfigException, self).__init__(message)
        if errors is None:
            errors = []
        if isinstance(errors, Exception):
            self.errors = [errors]
        else:
            self.errors = errors


class FrklistException(Exception):
    """Base exception class for nsbl."""

    def __init__(self, message):

        super(FrklistException, self).__init__(message)


class FrklistConfigException(FrklistException):

    def __init__(self, message):

        super(FrklConfigException, self).__init__(message)
