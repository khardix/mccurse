"""Package command line interface."""

import curses

import click

from . import _
from .curse import Game, Mod
from .proxy import Authorization
from .tui import select_mod
from .util import default_data_dir


# Static data
MINECRAFT = {'id': 432, 'name': 'Minecraft'}


@click.group()
@click.pass_context
def cli(ctx):
    """Minecraft Curse CLI client."""

    # Initialize terminal for querying
    curses.setupterm()

    # Add contextual values
    ctx.obj = {
        # Data directory
        'datadir': default_data_dir(),
        # Authentication file
        'authfile': default_data_dir() / 'token.yaml',
    }


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


@cli.command()
@click.option(
    '--user', '-u', prompt=_('Curse user name or email'),
    help=_('Curse user name or email')+'.',
)
@click.password_option(
    help=_('Curse password')+'.',
)
@click.pass_obj
def auth(ctx, user, password):
    """Authenticate user in Curse network."""

    token = Authorization.login(user, password)

    with ctx['authfile'].open(mode='w', encoding='utf-8') as file:
        token.dump(file)
