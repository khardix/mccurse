"""Command line interface to the package."""

import curses
from contextlib import contextmanager
from functools import partial
from logging import ERROR, INFO
from pathlib import Path
from typing import Generator

import click
import requests

from . import _, log
from .addon import Mod, Release
from .exceptions import UserReport, AlreadyUpToDate
from .curse import Game
from .pack import ModPack
from .proxy import Authorization
from .tui import select_mod
from .util import default_data_dir


# Customized path types
custom_path = partial(click.Path, resolve_path=True, path_type=str)
writable_file = partial(custom_path, writable=True, dir_okay=False)
writable_dir = partial(custom_path, writable=True, file_okay=False)


# Mod-pack context
@contextmanager
def modpack_file(path: Path) -> Generator[ModPack, None, None]:
    """Context manager for manipulation of existing mod-pack.

    Keyword arguments:
        path: Path to the existing ModPack file, which should be provided.

    Yields:
        ModPack loaded from path. If no exception occurs, the provided modpack
        is written (with changes) back to the file on context exit.
    """

    with path.open(encoding='utf-8', mode='r') as istream:
        mp = ModPack.load(istream)

    yield mp

    with path.open(encoding='utf-8', mode='w') as ostream:
        mp.dump(ostream)


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


# Shared option -- location of mod-pack data
pack_option = click.option(
    '--pack', help=_('Path to the mod-pack metadata file.'),
    type=writable_file(),
    default='modpack.yml',
)

# Shared option -- minimal release of a mod to consider
release_option = click.option(
    '--release', help=_('Minimal acceptable release type of a mod.'),
    type=click.Choice(('alpha', 'beta', 'release')), default='release',
)


@cli.command()
@pack_option
@click.option(
    '--path', help=_('Path to the storage directory for managed mods.'),
    type=writable_dir(exists=True), default='mods',
)
@click.option('--gamever', '-v', help=_('Version of the game to create mod-pack for.'))
@click.pass_obj
def new(ctx, pack, path, gamever):
    """Create and initialize a new mod-pack."""

    # Check file system state
    pack_path = Path(pack)
    mods_path = Path(path)

    if not pack_path.parent.exists():
        msg = _('Mod-pack directory does not exists: {}').format(pack_path.parent)
        raise UserReport(msg)
    # Mods path existence is checked by click

    # Setup game fro the mod-pack
    game = ctx['default_game']
    if gamever is not None:
        game.version = gamever

    with pack_path.open(mode='w', encoding='utf-8') as stream:
        mp = ModPack(game, mods_path.relative_to(pack_path.parent))
        mp.dump(stream)


@cli.command()
@pack_option
@release_option
@click.argument('mod')
@click.pass_obj
def install(ctx, pack, release, mod):
    """Install new MOD into a mod-pack."""

    with modpack_file(Path(pack)) as pack:
        moddb = pack.game.database
        mod = Mod.find(moddb.session(), mod)

        proxy_session = requests.Session()
        with ctx['token_path'].open(encoding='utf-8') as token:
            proxy_session.auth = Authorization.load(token)

        changes = pack.install_changes(
            mod=mod,
            min_release=Release[release.capitalize()],
            session=proxy_session,
        )
        pack.apply(changes)


@cli.command()
@pack_option
@click.argument('mod')
def remove(pack, mod):
    """Remove a MOD from a mod-pack."""

    with modpack_file(Path(pack)) as pack:
        moddb = pack.game.database
        mod = Mod.find(moddb.session(), mod)

        changes = pack.remove_changes(mod)
        pack.apply(changes)


@cli.command()
@pack_option
@release_option
@click.argument('mod')
@click.pass_obj
def upgrade(ctx, pack, release, mod):
    """Upgrade MOD and its dependencies."""

    with modpack_file(Path(pack)) as pack:
        moddb = pack.game.database
        mod = Mod.find(moddb.session(), mod)

        proxy_session = requests.Session()
        with ctx['token_path'].open(encoding='utf-8') as token:
            proxy_session.auth = Authorization.load(token)

        changes = pack.upgrade_changes(
            mod=mod,
            min_release=Release[release.capitalize()],
            session=proxy_session,
        )
        if not changes:
            raise AlreadyUpToDate(mod.name)

        pack.apply(changes)
