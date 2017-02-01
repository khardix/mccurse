.. image:: https://img.shields.io/travis/khardix/mccurse.svg
   :target: https://travis-ci.org/khardix/mccurse
.. image:: https://img.shields.io/pypi/v/mccurse.svg
   :target: https://pypi.python.org/pypi/mccurse
.. image:: https://img.shields.io/pypi/pyversions/mccurse.svg
   :target: https://pypi.python.org/pypi/mccurse
.. image:: https://img.shields.io/pypi/l/mccurse.svg
   :target: https://pypi.python.org/pypi/mccurse
.. image:: https://img.shields.io/pypi/status/mccurse.svg
   :target: https://pypi.python.org/pypi/mccurse
.. image:: https://img.shields.io/badge/SayThanks.io-%E2%98%BC-1EAEDB.svg
   :target: https://saythanks.io/to/khardix

Minecraft Curse CLI Client
==========================

This project is my humble attempt at creating an automated way of installing,
updating and managing mods for my Minecraft games. Using 
`Curse.RestProxy <https://github.com/amcoder/Curse.RestProxy>`_ as its primary
data source, it can find mods and their updates on Minecraft `CurseForge`_ and
automatically install them for you.

.. _CurseForge: https://minecraft.curseforge.com/

Usage
-----

The ``mccurse`` command provides various subcommands, described below.

Querying
^^^^^^^^

``mccurse search TEXT`` – Search available mods on `CurseForge`_, then presents
the user with list of possible matches. If the user choose one of them, it opens
its project page in the default browser.

Mod Management
^^^^^^^^^^^^^^

All the commands below presume that they are run in the profile directory of
a Minecraft instance.

``mccurse auth`` – Authenticate with your Curse account and store the auth token
for later use.

``mccurse new VERSION`` – Initialize new metadata file for current profile,
which will hold all the necessary info for installed mods. ``VERSION`` is the
Minecraft version of the instance (i.e. ``1.10.2``).

``mccurse install MOD`` – Install new mod, including its required dependencies,
to the current Minecraft instance.

``mccurse upgrade [all|MOD]`` – Upgrade mods to their latest version for current
game version. ``all`` upgrades all mods with available upgrades, ``MOD`` only
the specified one.

``mccurse remove MOD`` – Uninstall the ``MOD`` and its no longer needed
dependencies.

License
-------

``mccurse`` is released under the terms of `GNU Affero General Public License
version 3 or later <https://www.gnu.org/licenses/agpl-3.0.html>`_.
