"""A setup module for the mccurse package."""

from pathlib import Path
from setuptools import setup, find_packages
from typing import Generator, TextIO

here = Path(__file__).resolve().parent

# Long description
readme = here / 'README.rst'
with readme.open(encoding='utf-8') as rdm:
    long_description = rdm.read()


# Requirements
def extract_deps(fd: TextIO) -> Generator[str, None, None]:
    yield from (
        line for line in fd
        if line and not line.startswith(('#', 'git+'))
    )


deps = here / 'dependencies.txt'
test_deps = here / 'test-dependencies.txt'

with deps.open(encoding='utf-8') as d:
    install_requires = list(extract_deps(d))
with test_deps.open(encoding='utf-8') as td:
    test_requires = list(extract_deps(td))
    # XXX add missing dependency specified with git URL
    test_requires += ['pyfakefs>2.9']

setup_requires = [
    'setuptools_scm',
]

setup(
    name='mccurse',

    # Take version automatically from the git tag
    use_scm_version=True,

    description='Minecraft Curse CLI Client',
    long_description=long_description,

    url='https://github.com/khardix/mccurse',

    author='Jan "Khardix" Staněk',
    author_email='khardix@gmail.com',

    license='AGPLv3+',
    classifiers=[
        # Development status
        'Development Status :: 3 - Alpha',

        # Target audience
        'Intended Audience :: End Users/Desktop',
        'Topic :: Games/Entertainment',
        'Topic :: Utilities',

        # License
        'License :: OSI Approved :: GNU Affero General Public License v3 or later (AGPLv3+)',  # noqa: E501

        # Python versions
        'Programming Language :: Python :: 3 :: Only',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
    ],

    keywords='minecraft modding automation',

    packages=find_packages(exclude=('tests', 'docs')),

    # Requirements
    install_requires=install_requires,
    extras_require={
        'test': test_requires,
    },
    setup_requires=setup_requires,

    # Scripts entry points
    entry_points={
        'console_scripts': [
            'mccurse=mccurse.cli:cli',
        ],
    },
)
