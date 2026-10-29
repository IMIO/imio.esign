# -*- coding: utf-8 -*-
"""browser/settings tests for this package."""
from imio.esign import PLONE_VERSION
from imio.esign.browser.settings import validate_vat_number
from imio.esign.tests.base import BaseEsignTest
from zope.interface import Invalid

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


class TestSettingsForm(BaseEsignTest):

    def test_render(self):
        """The control panel renders, with a wysiwyg editor on the email content."""
        html = self.portal.restrictedTraverse("@@imio_esign_settings")()
        self.assertIn("form.widgets.signing_users_email_content", html)
        if PLONE_VERSION >= 5:
            self.assertIn("pat-tinymce", html)
