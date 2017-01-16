"""Interactive text user interface parts."""

import curses
from typing import Callable, Sequence, Iterable, Optional

import urwid

from .curse import Mod


#: Signature of valid menu callbacks
ModItemCallback = Callable[[Mod, urwid.Button], None]


class ModMenu(urwid.ListBox):
    """Menu presenting a choice from a list of :class:`Mod`s.

    The menu remembers which mod was chosen, in its :attr:`chosen`
    attribute (which defaults to None).
    """

    __slots__ = 'chosen',

    #: Color palette of the mod menu
    palette = [
        ('title',
            'dark green,bold', 'black', 'bold', '#0a0,bold', '#000'),
        ('title_focus',
            'white', 'dark green', 'underline', '#ff8', '#0a0'),
        ('description',
            'light gray', 'black'),
    ]

    class Item(urwid.Pile):
        """Display widget for a single :class:`Mod`."""

        def __init__(self, mod: Mod, *callbacks: Iterable[ModItemCallback]):
            """Wrap mod in the set of display widgets.

            Keyword arguments:
                mod: The :class:`Mod` to be wrapped.
                callbacks: The functions to be called when this object
                    is selected.
            """

            btn_prefix = '  ◈ '

            # Construct button (the selectable part)
            btn = urwid.Button('')
            btn._w = urwid.AttrMap(
                urwid.SelectableIcon([btn_prefix, mod.name], 2),
                'title', 'title_focus',
            )
            for callback in callbacks:
                urwid.connect_signal(btn, 'click', callback, user_args=[mod])

            # Construct the mod summary
            text = urwid.Padding(
                urwid.AttrMap(urwid.Text(mod.summary), 'description'),
                left=len(btn_prefix)*2,
            )

            pile = btn, text
            super().__init__(pile)

    def __init__(self, choices: Sequence[Mod]):
        """Create menu for choices.

        Keyword arguments:
            choices: The :class:`Mod`s to choose from.
        """

        items = [self.Item(m, self.choose, self.end_loop) for m in choices]
        super().__init__(urwid.SimpleFocusListWalker(items))

        self.chosen = None

    def choose(self, mod: Mod, btn: urwid.Button) -> None:
        """Record the choice.

        Keyword arguments:
            mod: The mod to record as the last choice.
            btn: Unused, exists for signature compatibility.
        """

        self.chosen = mod

    def end_loop(self, *unused) -> None:
        """End main event loop.

        Raises:
            urwid.ExitMainLoop: Every time it is called.
        """

        raise urwid.ExitMainLoop()


def exit_loop_on_q_esc(key: str):
    """End urwid.MainLoop on keypress of 'q' or 'esc'."""

    if key in {'q', 'Q', 'esc'}:
        raise urwid.ExitMainLoop()


def select_mod(
    choices: Sequence[Mod],
    header: Optional[str] = None,
    footer: Optional[str] = None,
) -> Optional[Mod]:
    """Present user with a TUI menu and return his choice.

    Keyword arguments:
        choices: The :class:`Mod`s to choose from.
        header: Optional menu heading.
        footer: Optional menu footing.

    Returns:
        The selected mod.
    """

    menu = ModMenu(choices)

    head = urwid.Text(('title', header), align='center') if header else None
    foot = urwid.Text(('description', footer), align='center') if footer else None  # noqa: E501

    if head or foot:
        top = urwid.Frame(menu, head, foot)
    else:
        top = menu

    try:
        colors = curses.tigetnum('colors')
    except curses.error:  # Uninitialized terminal
        colors = 16

    event_loop = urwid.MainLoop(
        top,
        palette=ModMenu.palette,
        unhandled_input=exit_loop_on_q_esc,
    )
    event_loop.screen.set_terminal_properties(colors=colors)
    event_loop.run()

    return menu.chosen
