"""Package command line interface."""

import curses
import logging
from collections import ChainMap
from pathlib import Path
from typing import Mapping

import click

from . import _, PKGDATA, log
from .curse import Game, Mod
from .pack import ModPack
from .proxy import Authorization
from .tui import select_mod
from .util import default_data_dir, yaml


def find_game(name: str, user_conf: Mapping = None) -> Mapping:
    """Find default parameters for a game.

    Keyword arguments:
        name: The game name to look for, case insensitive.
        user_conf: User-configured game defaults. This mapping should
            have the same structure as the package's game defaults
            configuration.

    Returns:
        Combined mapping of the parameter values, with user_conf
        taking precedence.
    """

    user_conf = dict() if user_conf is None else user_conf

    with (PKGDATA / 'supported_games.yaml').open(encoding='utf-8') as stream:
        package_defaults = yaml.load(stream)

    return ChainMap(
        user_conf.get(name.lower(), dict()),
        package_defaults.get(name.lower(), dict()),
    )


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
@click.version_option()
@click.option(
    '--game', '-g',
    type=click.STRING, default='Minecraft',
    help=_('Specify the game to mod.'),
)
@click.option(
    '--gamever', '-v',
    type=click.STRING, default=None,
    help=_('Specify the game version to mod.'),
)
@click.option(
    '--quiet', '-q', is_flag=True, default=False,
)
@click.pass_context
def cli(ctx, game, gamever, quiet):
    """Minecraft Curse CLI client."""

    # Resolve game parameters
    game_params = find_game(game)
    if not game_params:
        raise SystemExit(_("Unknown game '{game}'").format_map(locals()))
    if gamever:
        game_params['version'] = gamever

    # Initialize terminal for querying
    curses.setupterm()

    if not quiet:
        log.setLevel(logging.INFO)
    else:
        log.setLevel(logging.ERROR)

    # Add contextual values
    ctx.obj = {
        # Data directory
        'datadir': default_data_dir(),
        # Authentication file
        'authfile': default_data_dir() / 'token.yaml',
        # Game to work with
        'game': Game(name=game, **game_params),
    }


@cli.command()
@click.option(
    '--refresh', is_flag=True, default=False,
    # NOTE: Help for refresh flag
    help=_('Force refreshing of search data.')
)
@click.pass_obj
@click.argument('text', nargs=-1, type=str)
def search(ctx, refresh, text):
    """Search for TEXT in mods on CurseForge."""

    if not text:
        raise SystemExit(_('No text to search for!'))

    game = ctx['game']

    text = ' '.join(text)
    refresh = refresh or not game.have_fresh_data()

    if refresh:
        log.info(_('Refreshing search data, please wait…'))
        game.refresh_data()

    found = Mod.search(game.database.session(), text)

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
@click.pass_obj
def new(ctx, profile):
    """Create a new modpack for Minecraft VERSION."""

    game = ctx['game']
    profile = Path(str(profile))

    try:
        check_minecraft_dir(profile)
    except FileNotFoundError as err:
        msg = _('Profile directory is not valid: Missing {!s}').format(err)
        raise SystemExit(msg) from None

    modpack_file = profile / 'modpack.yaml'
    with modpack_file.open(mode='w', encoding='utf-8') as stream:
        ModPack.create(game).to_yaml(stream)
