"""Command line interface to the package."""

import curses
from logging import ERROR, INFO

import click

from . import _, log
from .addon import Mod
from .curse import Game
from .proxy import Authorization
from .tui import select_mod
from .util import default_data_dir


@click.group()
@click.version_option()
@click.option('--refresh', is_flag=True, default=False,
              help=_('Force refresh of existing mods list.'))
@click.option('--quiet', '-q', is_flag=True, default=False,
              help=_('Silence the process reporting.'))
@click.pass_context
def cli(ctx, quiet, refresh):
    """Unofficial CLI client for Minecraft Curse Forge."""

    # Context for the subcommands
    ctx.obj = {
        'default_game': Game.find('Minecraft'),  # Default game to query and use
        'token_path': default_data_dir() / 'token.yaml',  # Authorization token location
    }

    # Common setup

    # Setup terminal for querying (number of colors, etc.)
    curses.setupterm()
    # Setup appropriate logging level
    log.setLevel(INFO if not quiet else ERROR)

    # Refresh game data if necessary
    if refresh or not ctx.obj['default_game'].have_fresh_data():
        log.info(_('Refreshing game data, please wait.'))
        ctx.obj['default_game'].refresh_data()


@cli.command()
@click.option('--user', '-u', prompt=_('User name or email for Curse'),
              help=_('User name or email for Curse')+'.')
@click.password_option(help=_('Password for Curse')+'.')
@click.pass_obj
def auth(ctx, user, password):
    """Authenticate user for subsequent file operations."""

    token = Authorization.login(user, password)
    path = ctx['token_path']

    with path.open(mode='w', encoding='utf-8') as stream:
        token.dump(stream)


@cli.command()
@click.argument('name')
@click.pass_obj
def search(ctx, name):
    """Search Curse Forge for a mod named NAME."""

    search_result_description = {
        'header': _('Search results for "{name}"').format_map(locals()),
        'footer': _('Choose a mod to open its project page, or press [q] to quit.'),
    }

    moddb = ctx['default_game'].database

    results = Mod.search(moddb.session(), name)
    chosen = select_mod(results, **search_result_description)

    if chosen is not None:
        mod_page_url = 'https://www.curseforge.com/projects/{chosen.id}/'.format_map(locals())
        click.launch(mod_page_url)
