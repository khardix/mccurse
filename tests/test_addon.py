"""Tests for addon submodule."""

import pytest
from sqlalchemy.orm.session import Session as SQLSession

from mccurse import addon, curse


# Fixtures

@pytest.fixture
def filled_database(file_database) -> curse.Database:
    """Database with some mods filled in."""

    # Create structure
    addon.AddonBase.metadata.create_all(file_database.engine)

    # Add few mods
    session = SQLSession(bind=file_database.engine)
    session.add_all([
        addon.Mod(id=42, name='tested', summary="Mod under test"),
        addon.Mod(id=45, name='tester', summary="Validate tested mod"),
        addon.Mod(id=3, name='unrelated', summary="Dummy"),
    ])
    session.commit()

    return file_database


# Mod tests

def test_json_parsing():
    """Is the mod correctly constructed from JSON data?"""

    INPUT = {
      "Id": 74072,
      "Name": "Tinkers Construct",
      "Summary": "Modify all the things, then do it again!",
    }
    EXPECT = addon.Mod(
        id=74072,
        name="Tinkers Construct",
        summary="Modify all the things, then do it again!",
    )

    assert addon.Mod.from_json(INPUT) == EXPECT


def test_mod_search(filled_database):
    """Does the search return expected results?"""

    EXPECT_IDS = {42, 45}

    session = SQLSession(bind=filled_database.engine)
    selected = addon.Mod.search(session, 'Tested')

    assert {int(m.id) for m in selected} == EXPECT_IDS


def test_mod_find(filled_database):
    """Does the search find the correct mod or report correct error?"""

    session = SQLSession(bind=filled_database.engine)

    assert addon.Mod.find(session, 'Tested').id == 42

    with pytest.raises(addon.MultipleResultsFound):
        addon.Mod.find(session, 'test')

    with pytest.raises(addon.NoResultFound):
        addon.Mod.find(session, 'nonsense')
