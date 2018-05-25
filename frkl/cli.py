# -*- coding: utf-8 -*-

import collections
import logging
import pprint
import sys

import click
from six import string_types

from . import __version__ as VERSION
from .frkl_factory import factory

log = logging.getLogger("frkl")


class Config(object):
    """frkl configuration, holds things like aliases and such."""

    def __init__(self, configuration_dict=None):

        if not configuration_dict:
            configuration_dict = {}

        if isinstance(configuration_dict, dict):
            self.config = configuration_dict
        elif isinstance(configuration_dict, string_types):
            self.config = "XXX"
        else:
            raise Exception(
                "frkl configuration needs to be created using a dict object"
            )


@click.group(invoke_without_command=True)
@click.option("--version", help="the version of frkl you are using", is_flag=True)
@click.pass_context
def cli(ctx, version):
    """Console script for frkl"""

    if version:
        click.echo(VERSION)
        sys.exit(0)

    ctx.obj = {}


@cli.command("print-config")
@click.option(
    "--init",
    "-i",
    multiple=True,
    help="config to bootstrap the frkl object itself, if not provided, config strings need to contain at least one folder with init information, refer to documentation for more info",
)
@click.argument("config", required=False, nargs=-1)
@click.pass_context
def print_config(ctx, init, config):
    if not init:
        frkl_obj = init(config)
    else:
        frkl_obj = factory(init, config)

    result = frkl_obj.process()

    if isinstance(result, collections.Iterable):

        print("")
        print(
            "\n# ----------------------------------------\n".join(
                (pprint.pformat(x) for x in result)
            )
        )
        print("")

    else:
        print("")
        print(result)
        print("")


if __name__ == "__main__":
    cli()
