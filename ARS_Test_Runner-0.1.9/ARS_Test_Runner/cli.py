# -*- coding: utf-8 -*-

import click
import ast
import os
import sys
import asyncio
import datetime
from copy import deepcopy
from ARS_Test_Runner.semantic_test import run_semantic_test
from pkg_resources import get_distribution, DistributionNotFound
from warnings import simplefilter
# ignore all future warnings
simplefilter(action='ignore', category=FutureWarning)

try:
    __version__ = get_distribution("ARS_Test_Runner").version
except DistributionNotFound:
     # package is not installed
    pass

class PythonLiteralOption(click.Option):

    def type_cast_value(self, ctx, value):
        try:
            return ast.literal_eval(value)
        except:
            raise click.BadParameter(value)

@click.command(context_settings=dict(help_option_names=['-h', '--help']))
@click.version_option(version=__version__)
@click.option('--env', type=click.Choice(['dev', 'ci', 'test', 'prod'], case_sensitive=False))
@click.option('--predicate', type=click.STRING, help='default: treats', default='treats')
@click.option('--runner_setting', cls=PythonLiteralOption, help='creative mode indicator(inferred)')
@click.option('--expected_output', cls=PythonLiteralOption, type=click.Choice(['TopAnswer', 'Acceptable', 'BadButForgivable', 'NeverShow'], case_sensitive=False))
@click.option('--biolink_object_aspect_qualifier', type=click.STRING, help='aspect qualifier', default="")
@click.option('--biolink_object_direction_qualifier', type=click.STRING, help='direction qualifier', default="")
@click.option('--input_category', type=click.STRING, help='Input Type Category', default="")
@click.option('--input_curie', type=click.STRING, help='Input Curie', default='biolink:Disease')
@click.option('--output_curie', cls=PythonLiteralOption, help='Output Curie (can be a list)')

def main(env, predicate, runner_setting, expected_output,biolink_object_aspect_qualifier, biolink_object_direction_qualifier, input_category, input_curie, output_curie, ):

    current_time = datetime.datetime.now()
    formatted_time = current_time.strftime('%H:%M:%S')

    click.echo(f"started performing Single Level ARS_Test Analysis at {formatted_time}")
    #pylint: disable=too-many-arguments
    click.echo(asyncio.run(run_semantic_test(env, predicate, runner_setting, expected_output, biolink_object_aspect_qualifier, biolink_object_direction_qualifier, input_category, input_curie, output_curie)))
    endtime = datetime.datetime.now()
    click.echo(f"finished running the pipeline at {endtime}")

