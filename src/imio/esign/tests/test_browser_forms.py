# -*- coding: utf-8 -*-
"""Browser forms tests for this package."""
from imio.esign.browser.forms import CreateCustomSessionForm
from imio.esign.tests.base import BaseEsignTest
from imio.esign.tests.base import clear_status_messages
from imio.esign.utils import get_session_annotation
from mock import Mock
from mock import patch
from plone import api
from Products.statusmessages.interfaces import IStatusMessage


HP_UID_PREFIX = "hp-uid-"


def _make_mock_hp(userid, fullname, position_title):
    """Create a mock held_position with linked person."""
    mock_person = Mock()
    mock_person.userid = userid
    mock_person.get_title.return_value = fullname
    mock_hp = Mock()
    mock_hp.get_person.return_value = mock_person
    mock_hp.get_full_title.return_value = position_title
    return mock_hp


class TestCreateCustomSessionForm(BaseEsignTest):
    """Tests for CreateCustomSessionForm."""

    def setUp(self):
        super(TestCreateCustomSessionForm, self).setUp()
        api.user.create(email="signer1@sign.com", username="signer1", password="password1")  # noqa: S106
        api.user.create(email="signer2@sign.com", username="signer2", password="password2")  # noqa: S106
        self.form = CreateCustomSessionForm(self.portal, self.request)
        self.hp1 = _make_mock_hp("signer1", "First Signer", u"First Signer, Agent (My Org)")
        self.hp2 = _make_mock_hp("signer2", "Second Signer", u"Second Signer, Agent (My Org)")
        self.hp1_uid = HP_UID_PREFIX + "signer1"
        self.hp2_uid = HP_UID_PREFIX + "signer2"
        self._hp_map = {
            self.hp1_uid: self.hp1,
            self.hp2_uid: self.hp2,
        }

    def _uuid_to_object(self, uid, unrestricted=False):
        return self._hp_map.get(uid)

    def _call_handleCreate(self, data, errors=()):
        """Call handleCreate with mocked extractData and uuidToObject."""
        with patch.object(self.form, "extractData", return_value=(data, errors)):
            with patch("imio.esign.browser.forms.uuidToObject", side_effect=self._uuid_to_object):
                self.form.handleCreate(self.form, None)

    def test_extract_signer_info(self):
        """HP UID → (userid, email, fullname, position); no person → None; unknown UID → None."""
        # --- valid held_position ---
        with patch("imio.esign.browser.forms.uuidToObject", side_effect=self._uuid_to_object):
            result = self.form.extract_signer_info(self.hp1_uid)
        self.assertEqual(result, ("signer1", "signer1@sign.com", "First Signer", u"First Signer, Agent (My Org)"))
        self.hp1.get_person.assert_called()
        self.hp1.get_full_title.assert_called_with(first_index=1)

        # --- held_position with no person userid ---
        mock_hp_no_user = _make_mock_hp("", "Nobody", u"Nobody (Org)")
        with patch("imio.esign.browser.forms.uuidToObject", return_value=mock_hp_no_user):
            result = self.form.extract_signer_info("hp-uid-nouser")
        self.assertIsNone(result)

        # --- unknown UID ---
        with patch("imio.esign.browser.forms.uuidToObject", return_value=None):
            result = self.form.extract_signer_info("nonexistent-uid")
        self.assertIsNone(result)

    def test_handleCreate(self):
        """Validation errors → early return; no valid signers → warning;
        valid signers → session created + success message + redirect;
        mixed valid/invalid → only valid; seal and title passed through.
        """
        expected_redirect = self.portal.absolute_url() + "/@@parapheo"

        # --- validation errors: early return, no session created ---
        self._call_handleCreate(data={}, errors=("some error",))
        annot = get_session_annotation()
        self.assertEqual(len(annot["sessions"]), 0)
        messages = IStatusMessage(self.request).show()
        self.assertEqual(len(messages), 0)
        clear_status_messages(self.request)

        # --- no valid signers: warning message, no session ---
        self._call_handleCreate(
            data={"signers": {"nonexistent-uid"}, "seal": False, "title": u"Test"}
        )
        messages = IStatusMessage(self.request).show()
        self.assertEqual(len(messages), 1)
        self.assertIn("No valid signers selected", messages[0].message)
        self.assertEqual(messages[0].type, "warning")
        self.assertEqual(len(annot["sessions"]), 0)
        clear_status_messages(self.request)

        # --- empty signers set: same warning ---
        self._call_handleCreate(
            data={"signers": set(), "seal": False, "title": u"Test"}
        )
        messages = IStatusMessage(self.request).show()
        self.assertIn("No valid signers selected", messages[0].message)
        self.assertEqual(len(annot["sessions"]), 0)
        clear_status_messages(self.request)

        # --- valid single signer: session created, success message, redirect ---
        self._call_handleCreate(
            data={"signers": {self.hp1_uid}, "seal": False, "title": u"My Session"}
        )
        self.assertEqual(len(annot["sessions"]), 1)
        session = annot["sessions"][0]
        self.assertEqual(len(session["signers"]), 1)
        self.assertEqual(session["signers"][0]["userid"], "signer1")
        self.assertEqual(session["signers"][0]["email"], "signer1@sign.com")
        self.assertEqual(session["signers"][0]["position"], u"First Signer, Agent (My Org)")
        self.assertFalse(session["seal"])
        self.assertEqual(session["title"], u"My Session")
        messages = IStatusMessage(self.request).show()
        self.assertIn("Custom session created successfully", messages[0].message)
        self.assertEqual(messages[0].type, "info")
        self.assertEqual(self.request.RESPONSE.getHeader("location"), expected_redirect)
        clear_status_messages(self.request)

        # --- mixed valid/invalid signers: only valid ones in session ---
        self._call_handleCreate(
            data={"signers": {self.hp1_uid, "nonexistent-uid", self.hp2_uid}, "seal": False, "title": u"Mixed"}
        )
        self.assertEqual(len(annot["sessions"]), 2)
        session = annot["sessions"][1]
        signer_userids = {s["userid"] for s in session["signers"]}
        self.assertEqual(signer_userids, {"signer1", "signer2"})
        self.assertEqual(len(session["signers"]), 2)
        clear_status_messages(self.request)

        # --- seal=True passed through ---
        self._call_handleCreate(
            data={"signers": {self.hp1_uid}, "seal": True, "title": u"Sealed"}
        )
        self.assertEqual(len(annot["sessions"]), 3)
        session = annot["sessions"][2]
        self.assertTrue(session["seal"])
        clear_status_messages(self.request)

    def test_handleCancel(self):
        """Cancel redirects to @@parapheo."""
        self.form.handleCancel(self.form, None)
        expected = self.portal.absolute_url() + "/@@parapheo"
        self.assertEqual(self.request.RESPONSE.getHeader("location"), expected)
