"""Package command line interface."""

import curses

import click

from . import _
from .curse import Game, Mod
from .tui import select_mod


# Static data
MINECRAFT = {'id': 432, 'name': 'Minecraft'}


@click.group()
def cli():
    """Minecraft Curse CLI client."""

    # Initialize terminal for querying
    curses.setupterm()


@cli.command()
@click.option(
    '--refresh', is_flag=True, default=False,
    # NOTE: Help for refresh flag
    help=_('Force refreshing of search data.')
)
@click.argument('text', nargs=-1, type=str)
def search(refresh, text):
    """Search for TEXT in mods on CurseForge."""

    if not text:
        raise SystemExit(_('No text to search for!'))

    mc = Game(**MINECRAFT)

    text = ' '.join(text)
    refresh = refresh or not mc.have_fresh_data()

    if refresh:
        click.echo(_('Refreshing search data, please wait…'), err=True)
        mc.refresh_data()

    found = Mod.search(mc.database.session(), text)

    title = _('Search results for "{text}"').format(text=text)
    instructions = _(
        'Choose mod to open its project page, or press [q] to quit.'
    )

    chosen = select_mod(found, title, instructions)
    if chosen is not None:
        project_url_fmt = 'https://www.curseforge.com/projects/{mod.id}/'
        click.launch(project_url_fmt.format(mod=chosen))
