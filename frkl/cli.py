# -*- coding: utf-8 -*-

import logging
import pprint
import sys

import click
import yaml
from six import string_types

from . import __version__ as VERSION
from .frkl import Frkl

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
@click.option('--frkl', '-f', multiple=True, help="config to bootstrap the frkl object itself")
@click.option('--version', help='the version of frkl you are using', is_flag=True)
@click.pass_context
def cli(ctx, frkl, version):
    """Console script for frkl"""

    if version:
        click.echo(VERSION)
        sys.exit(0)

    frkl_obj = Frkl.factory(frkl)

    ctx.obj = {}
    ctx.obj['frkl'] = frkl_obj


@cli.command("print-config")
@click.argument('config', required=False, nargs=-1)
@click.pass_context
def print_config(ctx, config):

    frkl = ctx.obj['frkl']
    frkl.set_configs(config)
    result = frkl.process()
    print(yaml.dump(result, default_flow_style=False))


if __name__ == "__main__":
    cli()
