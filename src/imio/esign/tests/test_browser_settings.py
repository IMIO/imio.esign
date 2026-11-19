# -*- coding: utf-8 -*-
"""browser/settings tests for this package."""
from imio.esign.browser.settings import IImioEsignSettings
from imio.esign.browser.settings import ImioEsignSettings
from imio.esign.browser.settings import validate_vat_number
from imio.esign.config import get_esign_registry_signers_order
from imio.esign.config import set_esign_registry_signers_order
from imio.esign.tests.base import BaseEsignTest
from zope.interface import Invalid
from zope.schema import ASCIILine

import unittest


class TestValidateVatNumber(unittest.TestCase):

    def test_validate_vat_number(self):
        """validate_vat_number: returns True for valid/empty, raises Invalid for bad format or checksum."""
        # empty values are accepted (required constraint is enforced by the field, not the validator)
        self.assertTrue(validate_vat_number(u""))
        self.assertTrue(validate_vat_number(None))

        # must start with BE
        with self.assertRaises(Invalid):
            validate_vat_number(u"NL0202239951")

        # must be exactly 12 characters
        with self.assertRaises(Invalid):
            validate_vat_number(u"BE020223995")   # 11 chars
        with self.assertRaises(Invalid):
            validate_vat_number(u"BE02022399510")  # 13 chars

        # only digits allowed after BE
        with self.assertRaises(Invalid):
            validate_vat_number(u"BE020223995X")

        # bad checksum: 97 - (2022399 % 97) = 51, not 99
        with self.assertRaises(Invalid):
            validate_vat_number(u"BE0202239999")

        # valid: 97 - (2022399 % 97) = 97 - 46 = 51
        self.assertTrue(validate_vat_number(u"BE0202239951"))


class TestIImioEsignSettings(BaseEsignTest):

    def test_signers_order(self):
        """Ids are stored unchecked: a registry import keeps the ones out of the vocabulary."""
        self.assertIsInstance(IImioEsignSettings["signers_order"].value_type, ASCIILine)
        self.register_signers("user1", "user2")
        set_esign_registry_signers_order(["user2", "user1"])
        self.register_signers("user1")
        self.portal.portal_setup.runImportStepFromProfile("profile-imio.esign:default", "plone.app.registry")
        self.assertEqual(get_esign_registry_signers_order(), ["user2", "user1"])


class TestImioEsignSettings(BaseEsignTest):

    def test_updateFields(self):
        """The signers order is chosen among the imio.esign.signers vocabulary."""
        self.register_signers("user1", "user2")
        form = ImioEsignSettings(self.portal, self.request)
        form.update()
        self.assertEqual(form.fields["signers_order"].field.value_type.vocabularyName, "imio.esign.signers")
        self.assertEqual([term.value for term in form.widgets["signers_order"].terms], ["user1", "user2"])
        # the registry schema is left untouched
        self.assertIsInstance(IImioEsignSettings["signers_order"].value_type, ASCIILine)
