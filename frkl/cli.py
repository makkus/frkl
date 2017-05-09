# -*- coding: utf-8 -*-

import click
from six import string_types
import sys
import logging
from frkl import Frkl

from . import __version__ as VERSION

log = logging.getLogger("frkl")

class Config(object):
    """frkl configuration, holds things like aliases and such."""

    def __init__(self, configuration_dict=None):

        if not configuration_dict:
            configuration_dict = {}

        if isinstance(configuration_dict, dict):
            self.config = configuration_dict
        elif isinstance(configuration_dict, string_types):
            self.config
        else:
            raise Exception("frkl configuration needs to be created using a dict object")


@click.group(invoke_without_command=True)
@click.option('--version', help='the version of frkl you are using', is_flag=True)
def cli(version):
    """Console script for frkl"""

    if version:
        click.echo(VERSION)
        sys.exit(0)

@cli.command("print-config")
@click.argument('config', required=False, nargs=-1)
def print_config(config):

    frkl = Frkl()
    print("XX")





if __name__ == "__main__":
    cli()


