# -*- coding: utf-8 -*-
"""browser/settings tests for this package."""
from imio.esign import PLONE_VERSION
from imio.esign.browser.settings import validate_vat_number
from imio.esign.tests.base import BaseEsignTest
from plone import api
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

    template = u'<p>Bonjour <span tal:content="python: user_data[\'fullname\']">FULLNAME</span></p>'

    def test_render(self):
        """The control panel renders, the email content (a TAL template) in a plain textarea."""
        api.portal.set_registry_record("imio.esign.signing_users_email_content", self.template)
        html = self.portal.restrictedTraverse("@@imio_esign_settings")()
        self.assertIn("form.widgets.signing_users_email_content", html)
        if PLONE_VERSION >= 5:
            # TinyMCE would strip the TAL on save
            self.assertNotIn("pat-tinymce", html)
            self.assertIn("tal:content=", html)

    def test_save(self):
        """Saving the form keeps the TAL template unchanged."""
        self.request.form.update({
            "form.widgets.enabled": [u"selected"],
            "form.widgets.enabled-empty-marker": u"1",
            "form.widgets.vat_number": u"BE0202239951",
            "form.widgets.max_session_size": u"100",
            "form.widgets.max_session_files": u"25",
            "form.widgets.signing_users_email_content": self.template,
            "form.buttons.save": u"Save",
        })
        form = self.portal.restrictedTraverse("@@imio_esign_settings").form_instance
        form.update()
        self.assertFalse(form.widgets.errors)
        self.assertEqual(api.portal.get_registry_record("imio.esign.signing_users_email_content"), self.template)
        self.assertEqual(api.portal.get_registry_record("imio.esign.vat_number"), u"BE0202239951")
