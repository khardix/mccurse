"""Package command line interface."""

import curses
from pathlib import Path

import click

from . import _
from .curse import Game, Mod
from .pack import ModPack
from .proxy import Authorization
from .tui import select_mod
from .util import default_data_dir


# Static data
MINECRAFT = {'id': 432, 'name': 'Minecraft'}


def check_minecraft_dir(root: Path) -> None:
    """Checks if the directory is a suitable space for minecraft mods.

    Keyword Arguments:
        root: The checked dir – should be a root dir of minecraft profile.

    Raises:
        FileNotFoundError: When some expected file or directory is not found.
    """

    mods_dir = root / 'mods'

    if not mods_dir.is_dir():
        raise FileNotFoundError(str(mods_dir))


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


@cli.command()
@click.option(
    '--profile', '-p', type=click.Path(exists=True, file_okay=False),
    default='.',
    help=_('Root profile directory')+'.',
)
@click.argument('version')
def new(profile, version):
    """Create a new modpack for Minecraft VERSION."""

    mc = Game(**MINECRAFT)
    profile = Path(str(profile))

    try:
        check_minecraft_dir(profile)
    except FileNotFoundError as err:
        msg = _('Profile directory is not valid: Missing {!s}').format(err)
        raise SystemExit(msg) from None

    modpack_file = profile / 'modpack.yaml'
    with modpack_file.open(mode='w', encoding='utf-8') as stream:
        ModPack.create(name=mc.name, version=version).to_yaml(stream)
