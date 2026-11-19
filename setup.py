# -*- coding: utf-8 -*-
"""Installer for the imio.esign package."""

from setuptools import find_packages
from setuptools import setup


long_description = "\n\n".join(
    [
        open("README.rst").read(),
        open("CONTRIBUTORS.rst").read(),
        open("CHANGES.rst").read(),
    ]
)


setup(
    name="imio.esign",
    version="1.0.5.dev0",
    description="Integration of IMIO esign webservice",
    long_description=long_description,
    # Get more from https://pypi.org/classifiers/
    classifiers=[
        "Environment :: Web Environment",
        "Framework :: Plone",
        "Framework :: Plone :: Addon",
        "Framework :: Plone :: 4.3",
        "Framework :: Plone :: 6.1",
        "Programming Language :: Python",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3.13",
        "Operating System :: OS Independent",
        "License :: OSI Approved :: GNU General Public License v2 (GPLv2)",
    ],
    keywords="Python Plone CMS",
    author="Stephan Geulette",
    author_email="s.geulette@imio.be",
    url="https://github.com/IMIO/imio.esign",
    project_urls={
        "PyPI": "https://pypi.org/project/imio.esign/",
        "Source": "https://github.com/IMIO/imio.esign",
        "Tracker": "https://github.com/IMIO/imio.esign/issues",
        # 'Documentation': 'https://imio.esign.readthedocs.io/en/latest/',
    },
    license="GPL version 2",
    packages=find_packages("src", exclude=["ez_setup"]),
    namespace_packages=["imio"],
    package_dir={"": "src"},
    include_package_data=True,
    zip_safe=False,
    install_requires=[
        "setuptools",
        # -*- Extra requirements: -*-
        "collective.compoundcriterion",
        "collective.eeafaceted.z3ctable",
        "collective.iconifiedcategory",
        "eea.facetednavigation",
        # "html" module on Python 2
        "future",
        "imio.annex",
        "imio.fpaudit",
        # path.is_test_url
        "imio.helpers>=1.3.14",
        "imio.prettylink",
        "imio.pyutils",
        "plone.api>=1.8.4",
        "plone.app.dexterity",
        "plone.restapi",
        "requests",
        "six",
        # "z3c.jbot",
        "z3c.table",
    ],
    extras_require={
        "test": [
            "plone.app.testing",
            # Plone KGS does not use this version, because it would break
            # Remove if your package shall be part of coredev.
            # plone_coredev tests as of 2016-04-01.
            "plone.testing>=5.0.0",
            "plone.app.contenttypes",
            "plone.app.robotframework[debug]",
            "mock",
        ],
    },
    entry_points="""
    [z3c.autoinclude.plugin]
    target = plone
    [console_scripts]
    cosi_esign_push_acroform = imio.esign.scripts.cosi_esign_push_acroform:main
    """,
)
