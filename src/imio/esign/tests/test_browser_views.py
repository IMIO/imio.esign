# -*- coding: utf-8 -*-
"""Browser views tests for this package."""
from AccessControl import Unauthorized
from collections import OrderedDict
from datetime import datetime
from datetime import timedelta
from imio.esign.browser.views import DownloadFileView
from imio.esign.browser.views import ExternalSessionCreateView
from imio.esign.browser.views import FacetedSessionInfoViewlet
from imio.esign.browser.views import ItemSessionInfoViewlet
from imio.esign.browser.views import SessionDeleteView
from imio.esign.browser.views import SigningUsersCsv
from imio.esign.config import set_esign_registry_signing_users_email_content
from imio.esign.tests.base import BaseEsignTest
from imio.esign.utils import add_files_to_session
from imio.esign.utils import get_session_annotation
from imio.pyutils.utils import shortuid_encode_id
from mock import Mock
from mock import patch
from plone import api
from plone.app.testing import logout
from plone.app.testing import setRoles
from plone.app.testing import TEST_USER_ID
from plone.testing import z2
from Products.statusmessages import STATUSMESSAGEKEY
from Products.statusmessages.interfaces import IStatusMessage
from zope.annotation.interfaces import IAnnotations

import json
import unittest


def _clear_status_messages(request):
    """Clear status messages from request annotations (needed after redirects since show() skips clearing on 3xx)."""
    annotations = IAnnotations(request)
    annotations[STATUSMESSAGEKEY] = None
    request.response.expireCookie(STATUSMESSAGEKEY, path="/")


class TestSessionDeleteView(BaseEsignTest):
    """Tests for SessionDeleteView."""

    def setUp(self):
        super(TestSessionDeleteView, self).setUp()
        api.user.create(email="user1@sign.com", username="user1", password="password1")  # noqa: S106
        self.folder = self.portal["folder0"]
        annex = self.portal["folder0"]["annex0"]
        signers = [("user1", "user1@sign.com", "User 1", "Position 1")]
        self.session_id, _session = add_files_to_session(signers, (annex.UID(),))
        self.view = SessionDeleteView(self.folder, self.request)

    def test_may_delete_session(self):
        """Manager: True. Member-only: False and raises Unauthorized on call."""
        # --- Manager: allowed ---
        self.assertTrue(self.view.may_delete_session())

        # --- Member-only: denied ---
        setRoles(self.portal, TEST_USER_ID, ["Member"])
        self.assertFalse(self.view.may_delete_session())
        with self.assertRaises(Unauthorized):
            self.view()

    def test_call(self):
        """Missing id → error + context URL; valid id → success + session removed; unknown id → error."""
        annot = get_session_annotation()

        # --- no session id ---
        self.view()
        self.assertEqual(len(annot["sessions"]), 1)
        self.assertIn(self.session_id, annot["sessions"])

        # --- unknown session id ---
        self.request.form["esign_session_id"] = "9999"
        self.view()
        self.assertEqual(len(annot["sessions"]), 1)
        self.assertIn(self.session_id, annot["sessions"])

        # --- valid session id ---
        self.request.other.pop("esign_session_id", None)
        self.request.form["esign_session_id"] = str(self.session_id)
        self.view()
        self.assertNotIn(self.session_id, annot["sessions"])


class TestExternalSessionCreateView(BaseEsignTest):
    """Tests for ExternalSessionCreateView."""

    def setUp(self):
        super(TestExternalSessionCreateView, self).setUp()
        api.user.create(email="user1@sign.com", username="user1", password="password1")  # noqa: S106
        self.folder = self.portal["folder0"]
        annex = self.portal["folder0"]["annex0"]
        signers = [("user1", "user1@sign.com", "User 1", "Position 1")]
        self.session_id, _session = add_files_to_session(signers, (annex.UID(),))
        self.view = ExternalSessionCreateView(self.folder, self.request)

    def test_may_create_external_sessions(self):
        """Manager: True. Member-only: False and raises Unauthorized on call."""
        # --- Manager ---
        self.assertTrue(self.view.may_create_external_sessions())

        # --- Member-only ---
        setRoles(self.portal, TEST_USER_ID, ["Member"])
        self.assertFalse(self.view.may_create_external_sessions())
        with self.assertRaises(Unauthorized):
            self.view()

    def test_call(self):
        """Missing id → error; sentinel strings → specific errors; 200 → success; non-200 → error.

        create_external_session mocked: HTTP tested in test_utils.py.
        """
        # --- no session id ---
        result = self.view()
        messages = IStatusMessage(self.request).show()
        self.assertIn("No session ID provided!", messages[0].message)
        self.assertEqual(messages[0].type, "error")
        self.assertEqual("http://nohost/plone/folder0/@@parapheo", result)
        _clear_status_messages(self.request)

        self.request.form["session_id"] = str(self.session_id)

        def _run(return_value):
            _clear_status_messages(self.request)
            with patch("imio.esign.browser.views.create_external_session", return_value=return_value):
                return ExternalSessionCreateView(self.folder, self.request)()

        # --- session not found sentinel ---
        _run("_session_not_found_")
        messages = IStatusMessage(self.request).show()
        self.assertIn("doesn't exist anymore", messages[0].message)
        self.assertEqual(messages[0].type, "error")

        # --- no seal code sentinel ---
        _run("_no_seal_code_")
        messages = IStatusMessage(self.request).show()
        self.assertIn("No seal code", messages[0].message)

        # --- no seal email sentinel ---
        _run("_no_seal_email_")
        messages = IStatusMessage(self.request).show()
        self.assertIn("No seal email", messages[0].message)

        # --- no files sentinel ---
        _run("_no_files_")
        messages = IStatusMessage(self.request).show()
        self.assertIn("No files", messages[0].message)

        # --- 200 success ---
        mock_ok = Mock()
        mock_ok.status_code = 200
        result = _run(mock_ok)
        messages = IStatusMessage(self.request).show()
        self.assertIn("External session sent successfully!", messages[0].message)
        self.assertEqual(messages[0].type, "info")
        self.assertEqual("http://nohost/plone/folder0/@@parapheo", result)

        # --- non-200 error ---
        mock_err = Mock()
        mock_err.status_code = 500
        mock_err.reason = "Server Error"
        mock_err.text = "oops"
        result = _run(mock_err)
        messages = IStatusMessage(self.request).show()
        self.assertIn("500", messages[0].message)
        self.assertEqual(messages[0].type, "error")
        self.assertEqual("http://nohost/plone/folder0/@@parapheo", result)


@unittest.skip("Test skipped")
class TestDownloadFileView(BaseEsignTest):
    """Tests for DownloadFileView."""

    def setUp(self):
        super(TestDownloadFileView, self).setUp()
        self.app = self.layer["app"]
        self.folder = self.portal["folder0"]
        self.test_annex = self.folder["annex0"]
        self.file_uid = self.test_annex.UID()
        self.encoded_uid = shortuid_encode_id(self.file_uid, separator="-", block_size=5)
        self.view = DownloadFileView(self.portal, self.request)

    def test_download_file(self):
        """Missing id, invalid id, unknown id, no file attr, expired download, valid download, traversal."""
        logout()
        self.assertIsNone(self.view.file_id)
        self.assertEqual(self.view.shortuid_separator, "-")
        self.assertEqual(self.view.named_blob_file_attribute, "file")

        # --- no file id ---
        self.assertIn("A file identifier must be passed in the url", self.view())

        # --- invalid format ---
        self.view.file_id = "$$$"
        self.assertIn("This file identifier is not correct", self.view())

        # --- valid format but non-existent UID ---
        self.view.file_id = "aabbccddee"
        self.assertIn("The corresponding file identifier cannot be retrieved", self.view())

        # --- object has no file attribute ---
        folder_uid = self.folder.UID()
        encoded_folder_uid = shortuid_encode_id(folder_uid, separator="-", block_size=5)
        self.view.file_id = encoded_folder_uid
        self.assertIn("The corresponding file content cannot be retrieved", self.view())

        # --- expired download ---
        self.view.file_id = self.encoded_uid
        self.view.download_time_delta = timedelta(days=1)
        self.test_annex.setModificationDate(datetime.now() - timedelta(days=3))
        self.assertIn("The download period for this file has expired", self.view())

        # --- date check disabled ---
        self.view.download_time_delta = None
        result = self.view()
        self.assertNotIn("The download period for this file has expired", result)
        self.assertIsInstance(result, str)

        # --- valid download ---
        self.view.download_time_delta = timedelta(days=7)
        result = self.view()
        self.assertIsInstance(result, str)
        self.assertTrue(len(result) > 0)
        self.assertTrue(result.startswith(b"%PDF") or result.startswith("%PDF"))
        response = self.request.RESPONSE
        self.assertIn("application/pdf", response.getHeader("Content-Type"))
        self.assertIn("inline", response.getHeader("Content-Disposition"))
        self.assertIn("annex0.pdf", response.getHeader("Content-Disposition"))
        self.assertTrue(int(response.getHeader("Content-Length")) > 0)

        # --- URL traversal ---
        browser = z2.Browser(self.app)
        portal_url = self.portal.absolute_url()
        browser.open("{}/download-file/{}".format(portal_url, "aabbccddee"))
        self.assertIn("The corresponding file identifier cannot be retrieved (aabbccddee)", browser.contents)
        browser.open("{}/download-file/{}".format(portal_url, "aabbccddee/ffgghh"))
        self.assertIn("The corresponding file identifier cannot be retrieved (aabbccddee)", browser.contents)
        browser.open("{}/download-file/{}".format(portal_url, "aabbccddee?param=value"))
        self.assertIn("The corresponding file identifier cannot be retrieved (aabbccddee)", browser.contents)


class TestSigningUsersCsv(BaseEsignTest):
    """Tests for SigningUsersCsv."""

    def setUp(self):
        super(TestSigningUsersCsv, self).setUp()
        self.user = api.user.create(email="signer@test.com", username="signer_user", password="password1")  # noqa: S106
        self.view = SigningUsersCsv(self.portal, self.request)

    def _user_data(self, user):
        return {
            "userid": user.getId(),
            "email": user.getProperty("email", ""),
            "lastname": "",
            "firstname": "",
            "fullname": user.getProperty("fullname", ""),
        }

    def test_filter_user(self):
        """No group → False; non-watchers group → False; watchers group → True;
        held_position with 'signer' usage → True.

        api.content.find mocked for held_position: held_position type not in this layer.
        """
        # --- not in any group ---
        self.assertFalse(self.view.filter_user(self._user_data(self.user)))

        # --- non-watchers group ---
        api.group.create(groupname="myservice_editors")
        api.group.add_user(groupname="myservice_editors", user=self.user)
        self.assertFalse(self.view.filter_user(self._user_data(self.user)))

        # --- watchers group ---
        api.group.create(groupname="myservice_watchers")
        api.group.add_user(groupname="myservice_watchers", user=self.user)
        self.assertTrue(self.view.filter_user(self._user_data(self.user)))

        # --- held_position with signer usage ---
        hp_user = api.user.create(email="hp@test.com", username="hp_user", password="password1")  # noqa: S106
        mock_hp = Mock()
        mock_hp.usages = ["signer"]
        mock_brain = Mock()
        mock_brain.getObject.return_value = mock_hp
        with patch(
            "imio.esign.browser.views.api.content.find",  # held_position type not in this layer
            return_value=[mock_brain],
        ):
            self.assertTrue(self.view.filter_user(self._user_data(hp_user)))

    def test_get_users_data(self):
        """Returns all users with duplicate-email flags; watchers/signers marked checked."""
        users_data, _duplicates = self.view.get_users_data()
        # Users sorted alphabetically by userid: signer_user < test_user_1_
        self.assertEqual(
            users_data,
            [
                {
                    "checked": False,
                    "firstname": u"",
                    "lastname": u"signer_user",
                    "userid": "signer_user",
                    "has_duplicate_email": False,
                    "fullname": "",
                    "email": "signer@test.com",
                },
                {
                    "checked": False,
                    "firstname": u"",
                    "lastname": u"test_user_1_",
                    "userid": "test_user_1_",
                    "has_duplicate_email": False,
                    "fullname": "",
                    "email": "",
                },
            ],
        )

        # --- duplicate emails ---
        api.user.create(email="signer@test.com", username="signer_user2", password="password1")  # noqa: S106
        users_data, duplicates = self.view.get_users_data()
        self.assertEqual(
            users_data,
            [
                {
                    "checked": False,
                    "firstname": u"",
                    "lastname": u"signer_user",
                    "userid": "signer_user",
                    "has_duplicate_email": True,
                    "fullname": "",
                    "email": "signer@test.com",
                },
                {
                    "checked": False,
                    "firstname": u"",
                    "lastname": u"signer_user2",
                    "userid": "signer_user2",
                    "has_duplicate_email": True,
                    "fullname": "",
                    "email": "signer@test.com",
                },
                {
                    "checked": False,
                    "firstname": u"",
                    "lastname": u"test_user_1_",
                    "userid": "test_user_1_",
                    "has_duplicate_email": False,
                    "fullname": "",
                    "email": "",
                },
            ],
        )
        self.assertEqual(duplicates, {"signer@test.com": ["signer_user", "signer_user2"]})

        # --- watchers group member marked checked ---
        api.group.create(groupname="myservice_watchers")
        api.group.add_user(groupname="myservice_watchers", user=self.user)
        users_data, _duplicates = self.view.get_users_data()
        self.assertEqual(
            users_data,
            [
                {
                    "checked": True,
                    "firstname": u"",
                    "lastname": u"signer_user",
                    "userid": "signer_user",
                    "has_duplicate_email": True,
                    "fullname": "",
                    "email": "signer@test.com",
                },
                {
                    "checked": False,
                    "firstname": u"",
                    "lastname": u"signer_user2",
                    "userid": "signer_user2",
                    "has_duplicate_email": True,
                    "fullname": "",
                    "email": "signer@test.com",
                },
                {
                    "checked": False,
                    "firstname": u"",
                    "lastname": u"test_user_1_",
                    "userid": "test_user_1_",
                    "has_duplicate_email": False,
                    "fullname": "",
                    "email": "",
                },
            ],
        )

    def test_get_selected_userids(self):
        """Valid JSON → list; absent → []; bad JSON → []."""
        self.assertEqual(self.view._get_selected_userids(), [])

        self.request.form["selected_users"] = json.dumps(["user1", "user2"])
        self.assertEqual(self.view._get_selected_userids(), ["user1", "user2"])

        # request.get() promotes form values to request.other; clear both to reset
        self.request.other.pop("selected_users", None)
        self.request.form["selected_users"] = "not-valid-json"
        self.assertEqual(self.view._get_selected_userids(), [])

    def test_download_csv(self):
        """No selection → warning; valid selection → CSV with headers."""
        # --- no users ---
        self.view._download_csv()
        messages = IStatusMessage(self.request).show()
        self.assertIn("No users selected", messages[0].message)
        self.assertEqual(messages[0].type, "warning")
        _clear_status_messages(self.request)

        # --- valid selection ---
        # request.get() promotes form values to request.other; clear to prevent stale cache
        self.request.other.pop("selected_users", None)
        self.request.form["selected_users"] = json.dumps([self.user.getId()])
        result = self.view._download_csv()
        self.assertEqual(
            result,
            "userid,email,lastname,firstname,fullname\r\nsigner_user,signer@test.com,signer_user,,\r\n",
        )
        self.assertIn("text/csv", self.request.RESPONSE.getHeader("Content-Type"))

    def test_send_emails(self):
        """No selection → warning; no content → error; no from address → error; success."""
        # --- no users ---
        self.view._send_emails()
        messages = IStatusMessage(self.request).show()
        self.assertIn("No users selected", messages[0].message)
        self.assertEqual(messages[0].type, "warning")
        _clear_status_messages(self.request)

        # request.get() promotes form values to request.other; clear to prevent stale cache
        self.request.other.pop("selected_users", None)
        self.request.form["selected_users"] = json.dumps([self.user.getId()])

        # --- email content not configured ---
        set_esign_registry_signing_users_email_content(u"")
        self.view._send_emails()
        messages = IStatusMessage(self.request).show()
        self.assertEqual(messages[0].message, u"Email content is not configured in the settings.")
        self.assertEqual(messages[0].type, "error")
        _clear_status_messages(self.request)

        # --- portal from email not configured ---
        set_esign_registry_signing_users_email_content(u"<p>Hello</p>")
        self.view._send_emails()
        messages = IStatusMessage(self.request).show()
        self.assertEqual(messages[0].message, u"Portal from email is not configured.")
        self.assertEqual(messages[0].type, "error")
        _clear_status_messages(self.request)

        # --- success ---
        self.portal.manage_changeProperties({"email_from_address": "from@test.com"})
        with patch("imio.esign.browser.views.send_email", return_value=(True, None)):  # real SMTP call
            self.view._send_emails()
        messages = IStatusMessage(self.request).show()
        success_msgs = [m for m in messages if m.type == "info"]
        self.assertEqual(len(success_msgs), 1)
        self.assertIn("Emails sent successfully", success_msgs[0].message)
        _clear_status_messages(self.request)

        # --- user with no email address ---
        no_email_user = api.user.create(
            email="placeholder@test.com", username="no_email_user", password="password1"  # noqa: S106
        )
        no_email_user.setMemberProperties({"email": ""})
        self.request.other.pop("selected_users", None)
        self.request.form["selected_users"] = json.dumps([no_email_user.getId()])
        self.view._send_emails()
        messages = IStatusMessage(self.request).show()
        no_email_msgs = [m for m in messages if "no email address" in m.message]
        self.assertEqual(len(no_email_msgs), 1)
        self.assertEqual(no_email_msgs[0].type, "warning")

    def test_render_email_content(self):
        """TAL template is evaluated with user_data substitutions."""
        template = u"<p tal:content=\"python: user_data['fullname']\">NAME</p>"
        user_data = {
            "userid": "testuser",
            "email": "test@test.com",
            "lastname": "Smith",
            "firstname": "John",
            "fullname": "John Smith",
        }
        result = self.view._render_email_content(template, user_data)
        self.assertEqual(result, u"<p>John Smith</p>")


class TestFacetedSessionInfoViewlet(BaseEsignTest):
    """Tests for FacetedSessionInfoViewlet."""

    def setUp(self):
        super(TestFacetedSessionInfoViewlet, self).setUp()
        self.folder = self.portal["folder0"]
        self.annex = self.portal["folder0"]["annex0"]
        self.signers = [("user1", "user1@sign.com", "User 1", "Position 1")]
        self.collection_uid = "test-collection-uid"

    def _make_viewlet(self, uid="test-collection-uid"):
        class _ConcreteFacetedSessionInfoViewlet(FacetedSessionInfoViewlet):
            """Minimal concrete subclass for testing FacetedSessionInfoViewlet."""

            _sessions_collection_uid = "test-collection-uid"

            @property
            def sessions_collection_uid(self):
                return self._sessions_collection_uid

            def index(self):
                return "<rendered/>"

        v = _ConcreteFacetedSessionInfoViewlet(self.folder, self.request, None, None)
        v._sessions_collection_uid = uid
        return v

    def test_available(self):
        """False when sessions_collection_uid is None; True when set."""
        self.assertFalse(self._make_viewlet(uid=None).available())
        self.assertTrue(self._make_viewlet().available())

    def test_sessions(self):
        """sessions CachedProperty: {} for missing/invalid/unknown id; {id: info} for known id."""
        # --- no esign_session_id[] param ---
        self.assertEqual(self._make_viewlet().sessions, {})

        # --- non-integer value ---
        self.request.form["esign_session_id[]"] = "not-an-int"
        self.assertEqual(self._make_viewlet().sessions, {})

        # --- valid integer but no matching session ---
        self.request.form["esign_session_id[]"] = "999"
        self.assertEqual(self._make_viewlet().sessions, {})

        # --- valid session id → {session_id: session_info} ---
        sid, session = add_files_to_session(self.signers, [self.annex.UID()])
        self.request.form["esign_session_id[]"] = str(sid)
        sessions = self._make_viewlet().sessions
        self.assertEqual(list(sessions.keys()), [sid])
        self.assertEqual(sessions[sid]["sign_id"], session["sign_id"])

    def test_render(self):
        """'': c1[] absent or non-matching; real render_table() when no session;
        index() when session selected.

        Sessions annotation is empty when the "no session selected" branch runs, so
        ActionsColumn.renderCell / get_dashboard_link are never reached — no mock needed.
        """
        # --- c1[] absent → '' ---
        self.assertEqual(self._make_viewlet().render(), "")

        # --- c1[] non-matching → '' ---
        self.request.form["c1[]"] = "other-uid"
        self.assertEqual(self._make_viewlet().render(), "")

        # --- c1[] matches (right collection), no session selected → sessions_listing_view.render_table() ---
        self.request.form["c1[]"] = self.collection_uid
        result = self._make_viewlet().render()
        self.assertIn("<table", result)

        # --- c1[] matches (right collection), session selected → index() ---
        sid, _session = add_files_to_session(self.signers, [self.annex.UID()])
        self.request.form["esign_session_id[]"] = str(sid)
        self.assertEqual(self._make_viewlet().render(), "<rendered/>")

    def test_get_table_rows(self):
        """Column 1 → session fields; column 2 → signer/link fields; unknown → []."""
        v = self._make_viewlet()
        self.assertEqual(v.get_table_rows(1), ["session_id", "state", "update_date", "sealed"])
        self.assertEqual(v.get_table_rows(2), ["external_link", "signers"])
        self.assertEqual(v.get_table_rows(99), [])

    def test_ext_session_link(self):
        """No sign_url → <span> with title; sign_url present → <a href>."""
        v = self._make_viewlet()

        # --- no sign_url: span ---
        session = {"sign_id": "012345600000", "sign_url": None, "title": u"My Session"}
        result = v.ext_session_link(session)
        self.assertEqual(result, u"<span>My Session</span>")

        # --- sign_url present: anchor ---
        session["sign_url"] = "https://sign.example.com/s/1"
        result = v.ext_session_link(session)
        self.assertEqual(result, u'<a href="https://sign.example.com/s/1" target="_blank">My Session</a>')

    def test_get_state_description(self):
        """Known state → non-empty translated string; unknown state → ''."""
        v = self._make_viewlet()
        self.assertTrue(len(v.get_state_description("draft")) > 0)
        self.assertEqual(v.get_state_description("unknown_state"), "")


class TestItemSessionInfoViewlet(BaseEsignTest):
    """Tests for ItemSessionInfoViewlet."""

    def setUp(self):
        super(TestItemSessionInfoViewlet, self).setUp()
        api.user.create(email="user1@sign.com", username="user1", password="password1")  # noqa: S106
        self.folder = self.portal["folder0"]
        self.annexes = [self.portal["folder0"]["annex0"], self.portal["folder0"]["annex2"]]
        self.signers = [("user1", "user1@sign.com", "User 1", "Position 1")]

    def test_sessions(self):
        """No files → empty OrderedDict + render ''; one session → one entry; two sessions → two entries."""
        # --- no files in annotation ---
        viewlet = ItemSessionInfoViewlet(self.folder, self.request, None, None)
        self.assertEqual(viewlet.sessions, OrderedDict())
        self.assertEqual(viewlet.render(), "")

        # --- all context files in one session ---
        add_files_to_session(self.signers, [self.annexes[0].UID()], discriminators=("a",))
        viewlet = ItemSessionInfoViewlet(self.folder, self.request, None, None)
        sessions = viewlet.sessions
        self.assertEqual(len(sessions), 1)
        self.assertEqual(list(sessions.keys()), [0])
        self.assertEqual(len(sessions[0]["files"]), 1)
        self.assertEqual(sessions[0]["files"][0]["uid"], self.annexes[0].UID())

        # --- files split across two sessions (different discriminators) ---
        add_files_to_session(self.signers, [self.annexes[1].UID()], discriminators=("b",))
        viewlet = ItemSessionInfoViewlet(self.folder, self.request, None, None)
        sessions = viewlet.sessions
        self.assertEqual(len(sessions), 2)
        self.assertEqual(list(sessions.keys()), [0, 1])


class TestSessionsListingView(BaseEsignTest):
    """Test SessionsListingView browser view."""

    def setUp(self):
        super(TestSessionsListingView, self).setUp()
        self.folder = self.portal["folder0"]
        annex = self.portal["folder0"]["annex0"]
        signers = [("user1", "user1@sign.com", "User 1", "Position 1")]
        add_files_to_session(signers, (annex.UID(),))

    def test_get_sessions(self):
        """Test obtain sessions and stored annotation not modified."""
        self.assertFalse("id" in get_session_annotation()['sessions'][0])
        view = self.portal.restrictedTraverse("@@parapheo")
        self.assertTrue(view.available())
        sessions = view.get_sessions()
        self.assertTrue("id" in sessions[0])
        self.assertFalse("id" in get_session_annotation()['sessions'][0])
        # get_dashboard_link will raise NotImplementedError
        with self.assertRaises(NotImplementedError):
            view()
