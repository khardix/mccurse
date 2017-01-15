"""Package command line interface."""

import click

from .curse import Game, Mod


# Static data
MINECRAFT = {'id': 432, 'name': 'Minecraft'}


@click.group()
def cli():
    """Minecraft Curse CLI client."""


@cli.command()
@click.option(
    '--refresh', is_flag=True, default=False,
    help='Force refreshing of search data.'
)
@click.argument('text', nargs=-1, type=str)
def search(refresh, text):
    """Search for TEXT in mods on CurseForge."""

    mc = Game(**MINECRAFT)

    text = ' '.join(text)
    refresh = refresh or not mc.have_fresh_data()

    if refresh:
        click.echo('Refreshing search data, please wait…', err=True)
        mc.refresh_data()

    mod_fmt = '{0.name}: {0.summary}'
    for mod in Mod.search(mc.database.session(), text):
        click.echo(mod_fmt.format(mod))


# If run as a package, run whole cli
cli()
