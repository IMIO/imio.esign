# -*- coding: utf-8 -*-
"""Setup tests for this package."""
from imio.esign import PLONE_VERSION
from imio.esign.testing import IMIO_ESIGN_INTEGRATION_TESTING  # noqa: E501
from plone import api
from plone.app.testing import setRoles
from plone.app.testing import TEST_USER_ID

import unittest


if PLONE_VERSION >= 5:
    from Products.CMFPlone.utils import get_installer


class TestSetup(unittest.TestCase):
    """Test that imio.esign is properly installed."""

    layer = IMIO_ESIGN_INTEGRATION_TESTING

    def setUp(self):
        """Custom shared utility setup for tests."""
        self.portal = self.layer["portal"]
        if PLONE_VERSION < 5:
            self.installer = api.portal.get_tool("portal_quickinstaller")
        else:
            self.installer = get_installer(self.portal, self.layer["request"])

    def test_product_installed(self):
        """Test if imio.esign is installed."""
        if PLONE_VERSION < 5:
            self.assertTrue(self.installer.isProductInstalled("imio.esign"))
        else:
            self.assertTrue(self.installer.is_product_installed("imio.esign"))

    def test_browserlayer(self):
        """Test that IImioEsignLayer is registered."""
        from imio.esign.interfaces import IImioEsignLayer
        from plone.browserlayer import utils

        self.assertIn(IImioEsignLayer, utils.registered_layers())


class TestUninstall(unittest.TestCase):

    layer = IMIO_ESIGN_INTEGRATION_TESTING

    def setUp(self):
        self.portal = self.layer["portal"]
        roles_before = api.user.get_roles(TEST_USER_ID)
        setRoles(self.portal, TEST_USER_ID, ["Manager"])
        if PLONE_VERSION < 5:
            self.installer = api.portal.get_tool("portal_quickinstaller")
            self.installer.uninstallProducts(["imio.esign"])
        else:
            self.installer = get_installer(self.portal, self.layer["request"])
            self.installer.uninstall_product("imio.esign")
        setRoles(self.portal, TEST_USER_ID, roles_before)

    def test_product_uninstalled(self):
        """Test if imio.esign is cleanly uninstalled."""
        if PLONE_VERSION < 5:
            self.assertFalse(self.installer.isProductInstalled("imio.esign"))
        else:
            self.assertFalse(self.installer.is_product_installed("imio.esign"))

    def test_browserlayer_removed(self):
        """Test that IImioEsignLayer is removed."""
        from imio.esign.interfaces import IImioEsignLayer
        from plone.browserlayer import utils

        self.assertNotIn(IImioEsignLayer, utils.registered_layers())
