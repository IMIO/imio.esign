# -*- coding: utf-8 -*-
"""Browser views tests for this package."""
from AccessControl import Unauthorized
from collections import OrderedDict
from collective.iconifiedcategory.utils import calculate_category_id
from datetime import datetime
from datetime import timedelta
from imio.esign.browser.views import DownloadFileView
from imio.esign.browser.views import ExternalSessionCreateView
from imio.esign.browser.views import ItemSessionInfoViewlet
from imio.esign.browser.views import SessionDeleteView
from imio.esign.browser.views import SessionsListingView
from imio.esign.browser.views import SigningUsersCsv
from imio.esign.config import set_esign_registry_signing_users_email_content
from imio.esign.testing import IMIO_ESIGN_FUNCTIONAL_TESTING
from imio.esign.testing import IMIO_ESIGN_INTEGRATION_TESTING
from imio.esign.utils import add_files_to_session
from imio.esign.utils import get_session_annotation
from imio.esign.utils import get_session_info
from imio.pyutils.utils import shortuid_encode_id
from mock import Mock
from mock import patch
from plone import api
from plone.app.testing import logout
from plone.app.testing import setRoles
from plone.app.testing import TEST_USER_ID
from plone.namedfile.file import NamedBlobFile
from plone.namedfile.file import NamedBlobImage
from plone.testing import z2
from Products.statusmessages.interfaces import IStatusMessage

import collective.iconifiedcategory
import json
import os
import transaction
import unittest


class _BaseSessionViewTest(unittest.TestCase):
    """Base test class with shared setUp for session view tests."""

    layer = IMIO_ESIGN_INTEGRATION_TESTING

    def setUp(self):
        self.portal = self.layer["portal"]
        self.request = self.layer["request"]
        self.request.form.clear()
        setRoles(self.portal, TEST_USER_ID, ["Manager"])

        # Create user for signing
        api.user.create(email="user1@sign.com", username="user1", password="password1")  # noqa: S106

        # Create content category configuration
        at_folder = api.content.create(
            container=self.portal,
            id="annexes_types",
            title="Annexes Types",
            type="ContentCategoryConfiguration",
            exclude_from_nav=True,
        )
        category_group = api.content.create(
            type="ContentCategoryGroup",
            title="Annexes",
            container=at_folder,
            id="annexes",
        )
        icon_path = os.path.join(
            os.path.dirname(collective.iconifiedcategory.__file__), "tests", "icône1.png"
        )
        with open(icon_path, "rb") as fl:
            api.content.create(
                type="ContentCategory",
                title="To sign",
                container=category_group,
                icon=NamedBlobImage(fl.read(), filename=u"icône1.png"),
                id="to_sign",
                predefined_title="To be signed",
                to_sign=True,
                show_preview=False,
            )

        # Create folder and annex
        self.folder = api.content.create(
            container=self.portal,
            type="Folder",
            id="test_folder",
            title="Test Folder",
        )
        tests_dir = os.path.dirname(__file__)
        with open(os.path.join(tests_dir, "annex1.pdf"), "rb") as f:
            annex = api.content.create(
                container=self.folder,
                type="annex",
                id="test_annex",
                title="Test Annex",
                content_category=calculate_category_id(
                    self.portal["annexes_types"]["annexes"]["to_sign"]
                ),
                scan_id="012345600000001",
                file=NamedBlobFile(
                    data=f.read(),
                    filename=u"annex1.pdf",
                    contentType="application/pdf",
                ),
            )
        self.annex_uid = annex.UID()

        # Seed a session in the annotation
        signers = [("user1", "user1@sign.com", "User 1", "Position 1")]
        self.session_id, _ = add_files_to_session(signers, (self.annex_uid,))


class TestSessionDeleteView(_BaseSessionViewTest):
    """Test SessionDeleteView browser view."""

    def test_may_delete_session(self):
        """Manager role grants may_delete_session."""
        view = SessionDeleteView(self.folder, self.request)
        self.assertTrue(view.may_delete_session())

    def test_may_delete_session_no_permission(self):
        """Member-only role denies may_delete_session."""
        setRoles(self.portal, TEST_USER_ID, ["Member"])
        view = SessionDeleteView(self.folder, self.request)
        self.assertFalse(view.may_delete_session())
        with self.assertRaises(Unauthorized):
            view()

    def test_call_no_session_id(self):
        """Missing esign_session_id produces an error message and redirects to context URL."""
        view = SessionDeleteView(self.folder, self.request)
        view()
        messages = IStatusMessage(self.request).show()
        self.assertEqual(len(messages), 1)
        self.assertIn("No session ID provided!", messages[0].message)
        self.assertEqual(messages[0].type, "error")
        location = self.request.RESPONSE.getHeader("location")
        self.assertEqual(location, self.folder.absolute_url())

    def test_call_session_exists(self):
        """Valid esign_session_id removes the session and shows a success message."""
        self.request.form["esign_session_id"] = str(self.session_id)
        view = SessionDeleteView(self.folder, self.request)
        view()
        messages = IStatusMessage(self.request).show()
        self.assertEqual(len(messages), 1)
        self.assertIn("Session deleted successfully!", messages[0].message)
        self.assertEqual(messages[0].type, "info")
        location = self.request.RESPONSE.getHeader("location")
        self.assertIn("@@parapheo", location)
        annotation = get_session_annotation()
        self.assertNotIn(self.session_id, annotation["sessions"])

    def test_call_session_not_found(self):
        """Non-existent esign_session_id shows an error and redirects to @@parapheo."""
        self.request.form["esign_session_id"] = "9999"
        view = SessionDeleteView(self.folder, self.request)
        view()
        messages = IStatusMessage(self.request).show()
        self.assertEqual(len(messages), 1)
        self.assertIn("Session not found!", messages[0].message)
        self.assertEqual(messages[0].type, "error")
        location = self.request.RESPONSE.getHeader("location")
        self.assertIn("@@parapheo", location)


class TestExternalSessionCreateView(_BaseSessionViewTest):
    """Test ExternalSessionCreateView browser view."""

    def test_may_create_external_sessions(self):
        """Manager role grants may_create_external_sessions."""
        view = ExternalSessionCreateView(self.folder, self.request)
        self.assertTrue(view.may_create_external_sessions())

    def test_call_unauthorized(self):
        """Calling view without permission raises Unauthorized."""
        setRoles(self.portal, TEST_USER_ID, ["Member"])
        view = ExternalSessionCreateView(self.folder, self.request)
        self.assertFalse(view.may_create_external_sessions())
        with self.assertRaises(Unauthorized):
            view()

    def test_call_no_session_id(self):
        """Missing session_id produces an error message and returns URL with @@parapheo."""
        view = ExternalSessionCreateView(self.folder, self.request)
        result = view()
        messages = IStatusMessage(self.request).show()
        self.assertEqual(len(messages), 1)
        self.assertIn("No session ID provided!", messages[0].message)
        self.assertEqual(messages[0].type, "error")
        self.assertIn("@@parapheo", result)

    def test_call_session_not_found(self):
        """create_external_session returning _session_not_found_ shows an error."""
        self.request.form["session_id"] = str(self.session_id)
        view = ExternalSessionCreateView(self.folder, self.request)
        with patch("imio.esign.browser.views.create_external_session") as mock_create:
            mock_create.return_value = "_session_not_found_"
            result = view()
        messages = IStatusMessage(self.request).show()
        self.assertEqual(len(messages), 1)
        self.assertIn("doesn't exist anymore", messages[0].message)
        self.assertEqual(messages[0].type, "error")
        self.assertIn("@@parapheo", result)

    def test_call_no_seal_code(self):
        """create_external_session returning _no_seal_code_ shows an error."""
        self.request.form["session_id"] = str(self.session_id)
        view = ExternalSessionCreateView(self.folder, self.request)
        with patch("imio.esign.browser.views.create_external_session") as mock_create:
            mock_create.return_value = "_no_seal_code_"
            result = view()
        messages = IStatusMessage(self.request).show()
        self.assertEqual(len(messages), 1)
        self.assertIn("No seal code", messages[0].message)
        self.assertEqual(messages[0].type, "error")
        self.assertIn("@@parapheo", result)

    def test_call_no_seal_email(self):
        """create_external_session returning _no_seal_email_ shows an error."""
        self.request.form["session_id"] = str(self.session_id)
        view = ExternalSessionCreateView(self.folder, self.request)
        with patch("imio.esign.browser.views.create_external_session") as mock_create:
            mock_create.return_value = "_no_seal_email_"
            result = view()
        messages = IStatusMessage(self.request).show()
        self.assertEqual(len(messages), 1)
        self.assertIn("No seal email", messages[0].message)
        self.assertEqual(messages[0].type, "error")
        self.assertIn("@@parapheo", result)

    def test_call_success(self):
        """create_external_session returning a 200 response shows a success message."""
        self.request.form["session_id"] = str(self.session_id)
        view = ExternalSessionCreateView(self.folder, self.request)
        mock_response = Mock()
        mock_response.status_code = 200
        with patch("imio.esign.browser.views.create_external_session") as mock_create:
            mock_create.return_value = mock_response
            result = view()
        messages = IStatusMessage(self.request).show()
        self.assertEqual(len(messages), 1)
        self.assertIn("External session sent successfully!", messages[0].message)
        self.assertEqual(messages[0].type, "info")
        self.assertIn("@@parapheo", result)

    def test_call_error_response(self):
        """create_external_session returning a non-200 response shows the status details."""
        self.request.form["session_id"] = str(self.session_id)
        view = ExternalSessionCreateView(self.folder, self.request)
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.reason = "Server Error"
        mock_response.text = "oops"
        with patch("imio.esign.browser.views.create_external_session") as mock_create:
            mock_create.return_value = mock_response
            result = view()
        messages = IStatusMessage(self.request).show()
        self.assertEqual(len(messages), 1)
        self.assertIn("500", messages[0].message)
        self.assertEqual(messages[0].type, "error")
        self.assertIn("@@parapheo", result)


@unittest.skip("Test skipped")
class TestDownloadFileView(unittest.TestCase):
    """Test DownloadFileView browser view."""

    layer = IMIO_ESIGN_FUNCTIONAL_TESTING

    def setUp(self):
        """Set up test fixtures."""
        self.app = self.layer["app"]
        self.portal = self.layer["portal"]
        self.request = self.layer["request"]
        setRoles(self.portal, TEST_USER_ID, ["Manager"])

        # Setup content category configuration (like in test_utils.py)
        at_folder = api.content.create(
            container=self.portal,
            id="annexes_types",
            title="Annexes Types",
            type="ContentCategoryConfiguration",
            exclude_from_nav=True,
        )
        category_group = api.content.create(
            type="ContentCategoryGroup",
            title="Annexes",
            container=at_folder,
            id="annexes",
        )
        icon_path = os.path.join(os.path.dirname(collective.iconifiedcategory.__file__), "tests", "icône1.png")
        with open(icon_path, "rb") as fl:
            api.content.create(
                type="ContentCategory",
                title="To sign",
                container=category_group,
                icon=NamedBlobImage(fl.read(), filename=u"icône1.png"),
                id="to_sign",
                predefined_title="To be signed",
                to_sign=True,
                show_preview=False,
            )

        # Create a folder to hold test annexes
        self.folder = api.content.create(
            container=self.portal,
            type="Folder",
            id="test_folder",
            title="Test Folder",
        )

        # Create test annexes with NamedBlobFile (Plone 4.3 Archetypes)
        tests_dir = os.path.dirname(__file__)
        pdf_file = "annex1.pdf"
        with open(os.path.join(tests_dir, pdf_file), "rb") as f:
            file_data = f.read()
            self.test_annex = api.content.create(
                container=self.folder,
                type="annex",
                id="test_annex",
                title="Test Annex",
                content_category="to_sign",
                file=NamedBlobFile(
                    data=file_data,
                    filename=u"test_document__uid.pdf",
                    contentType="application/pdf"
                ),
            )

        self.file_uid = self.test_annex.UID()
        self.encoded_uid = shortuid_encode_id(self.file_uid, separator="-", block_size=5)

        # Commit transaction for functional testing
        transaction.commit()

    def test_download_file_view(self):
        """Test DownloadFileView with various scenarios."""
        logout()  # anonymous usage

        # View exists and can be instantiated
        view = api.content.get_view("download-file", self.portal, self.request)
        self.assertIsInstance(view, DownloadFileView)
        view = DownloadFileView(self.portal, self.request)
        self.assertEqual(view.file_id, None)
        self.assertEqual(view.shortuid_separator, "-")
        self.assertEqual(view.named_blob_file_attribute, "file")

        # Download file without UID
        view = DownloadFileView(self.portal, self.request)
        result = view()
        self.assertIn("A file identifier must be passed in the url", result)
        # invalid UID format
        view.file_id = "$$$"
        result = view()
        self.assertIn("This file identifier is not correct", result)
        # valid format but non-existent UID
        view.file_id = "aabbccddee"
        result = view()
        self.assertIn("The corresponding file identifier cannot be retrieved", result)
        # download from object without file attribute
        folder_uid = self.folder.UID()
        encoded_folder_uid = shortuid_encode_id(folder_uid, separator="-", block_size=5)
        view.file_id = encoded_folder_uid
        result = view()
        self.assertIn("The corresponding file content cannot be retrieved", result)

        # valid id but file too old
        view.file_id = self.encoded_uid
        view.download_time_delta = timedelta(days=1)
        self.test_annex.setModificationDate(datetime.now() - timedelta(days=3))
        result = view()
        self.assertIn("The download period for this file has expired", result)
        view.download_time_delta = None  # Disable date verification
        result = view()
        self.assertNotIn("The download period for this file has expired", result)
        self.assertIsInstance(result, str)

        # Download file with valid UID
        view.file_id = self.encoded_uid
        view.download_time_delta = timedelta(days=7)
        result = view()
        # Check that we got binary data (the file content)
        self.assertIsInstance(result, str)  # In Python 2, binary data is str
        self.assertTrue(len(result) > 0)
        self.assertTrue(result.startswith(b"%PDF") or result.startswith("%PDF"))
        # Check response headers
        response = self.request.RESPONSE
        self.assertIn("application/pdf", response.getHeader("Content-Type"))
        self.assertIn("inline", response.getHeader("Content-Disposition"))
        self.assertIn("test_document.pdf", response.getHeader("Content-Disposition"))
        self.assertTrue(int(response.getHeader("Content-Length")) > 0)

        # Test URL traversal mechanism
        browser = z2.Browser(self.app)
        portal_url = self.portal.absolute_url()
        browser.open("{}/download-file/{}".format(portal_url, "aabbccddee"))
        self.assertIn("The corresponding file identifier cannot be retrieved (aabbccddee)", browser.contents)
        browser.open("{}/download-file/{}".format(portal_url, "aabbccddee/ffgghh"))
        self.assertIn("The corresponding file identifier cannot be retrieved (aabbccddee)", browser.contents)
        browser.open("{}/download-file/{}".format(portal_url, "aabbccddee?param=value"))
        self.assertIn("The corresponding file identifier cannot be retrieved (aabbccddee)", browser.contents)


class TestSigningUsersCsv(unittest.TestCase):
    """Tests for the SigningUsersCsv view."""

    layer = IMIO_ESIGN_INTEGRATION_TESTING

    def setUp(self):
        self.portal = self.layer["portal"]
        self.request = self.layer["request"]
        self.request.form.clear()
        setRoles(self.portal, TEST_USER_ID, ["Manager"])
        self.user = api.user.create(email="signer@test.com", username="signer_user", password="password1")  # noqa: S106

    def _make_user_data(self, user):
        return {
            "userid": user.getId(),
            "email": user.getProperty("email", ""),
            "lastname": "",
            "firstname": "",
            "fullname": user.getProperty("fullname", ""),
        }

    # --- filter_user ---

    def test_filter_user_in_watchers_group_returns_true(self):
        """User in a group ending with 'watchers' is included by default."""
        api.group.create(groupname="myservice_watchers")
        api.group.add_user(groupname="myservice_watchers", user=self.user)
        view = SigningUsersCsv(self.portal, self.request)
        self.assertTrue(view.filter_user(self._make_user_data(self.user)))

    def test_filter_user_not_in_any_group_returns_false(self):
        """User with no held_position and no watchers group is excluded."""
        view = SigningUsersCsv(self.portal, self.request)
        self.assertFalse(view.filter_user(self._make_user_data(self.user)))

    def test_filter_user_in_non_watchers_group_returns_false(self):
        """User in a group not ending with 'watchers' is excluded."""
        api.group.create(groupname="myservice_editors")
        api.group.add_user(groupname="myservice_editors", user=self.user)
        view = SigningUsersCsv(self.portal, self.request)
        self.assertFalse(view.filter_user(self._make_user_data(self.user)))

    def test_filter_user_with_signer_held_position_returns_true(self):
        """User with a held_position having 'signer' in usages is included by default."""
        mock_hp_obj = Mock()
        mock_hp_obj.usages = ["signer"]
        mock_brain = Mock()
        mock_brain.getObject.return_value = mock_hp_obj
        view = SigningUsersCsv(self.portal, self.request)
        with patch("imio.esign.browser.views.api.content.find", return_value=[mock_brain]):
            result = view.filter_user(self._make_user_data(self.user))
        self.assertTrue(result)

    # --- get_users_data ---

    def test_get_users_data(self):
        """Returns data for all users with duplicates."""
        view = SigningUsersCsv(self.portal, self.request)
        users_data, _duplicates = view.get_users_data()
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

        # Test duplicates
        api.user.create(email="signer@test.com", username="signer_user2", password="password1")  # noqa: S106
        view = SigningUsersCsv(self.portal, self.request)
        users_data, duplicates = view.get_users_data()
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

        # Signers and watchers users are sorted and checked
        api.group.create(groupname="myservice_watchers")
        api.group.add_user(groupname="myservice_watchers", user=self.user)
        view = SigningUsersCsv(self.portal, self.request)
        users_data, _duplicates = view.get_users_data()
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

    # --- _get_selected_userids ---

    def test_get_selected_userids_with_valid_json(self):
        """Parses a JSON array of user IDs from the request form."""
        self.request.form["selected_users"] = json.dumps(["user1", "user2"])
        view = SigningUsersCsv(self.portal, self.request)
        self.assertEqual(view._get_selected_userids(), ["user1", "user2"])

    def test_get_selected_userids_with_empty_param(self):
        """Returns empty list when selected_users is absent."""
        view = SigningUsersCsv(self.portal, self.request)
        self.assertEqual(view._get_selected_userids(), [])

    def test_get_selected_userids_with_invalid_json(self):
        """Returns empty list for malformed JSON."""
        self.request.form["selected_users"] = "not-valid-json"
        view = SigningUsersCsv(self.portal, self.request)
        self.assertEqual(view._get_selected_userids(), [])

    # --- _download_csv ---

    def test_download_csv_no_selected_users(self):
        """Shows warning and redirects when no users are selected."""
        view = SigningUsersCsv(self.portal, self.request)
        view._download_csv()
        messages = IStatusMessage(self.request).show()
        self.assertEqual(len(messages), 1)
        self.assertIn("No users selected", messages[0].message)
        self.assertEqual(messages[0].type, "warning")

    def test_download_csv_generates_csv(self):
        """Returns CSV content with headers and a row for each selected user."""
        self.request.form["selected_users"] = json.dumps([self.user.getId()])
        view = SigningUsersCsv(self.portal, self.request)
        result = view._download_csv()
        self.assertEqual(
            result, "userid,email,lastname,firstname,fullname\r\nsigner_user,signer@test.com,signer_user,,\r\n"
        )
        self.assertIn("text/csv", self.request.RESPONSE.getHeader("Content-Type"))

    # --- _send_emails ---

    def test_send_emails_no_selected_users(self):
        """Shows warning and redirects when no users are selected."""
        view = SigningUsersCsv(self.portal, self.request)
        view._send_emails()
        messages = IStatusMessage(self.request).show()
        self.assertEqual(len(messages), 1)
        self.assertIn("No users selected", messages[0].message)
        self.assertEqual(messages[0].type, "warning")

    def test_send_emails_no_email_content(self):
        """Shows error and redirects when signing users email content is not configured."""
        set_esign_registry_signing_users_email_content(u"")
        self.request.form["selected_users"] = json.dumps([self.user.getId()])
        view = SigningUsersCsv(self.portal, self.request)
        view._send_emails()
        messages = IStatusMessage(self.request).show()
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0].message, u"Email content is not configured in the settings.")
        self.assertEqual(messages[0].type, "error")

    def test_send_emails_no_portal_from_email(self):
        """Shows error and redirects to mail-controlpanel when portal from email is not set."""
        self.request.form["selected_users"] = json.dumps([self.user.getId()])
        view = SigningUsersCsv(self.portal, self.request)
        view._send_emails()
        messages = IStatusMessage(self.request).show()
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0].message, u"Portal from email is not configured.")
        self.assertEqual(messages[0].type, "error")

    def test_send_emails_success(self):
        """Sends emails to all selected users and shows a success message."""
        self.portal.manage_changeProperties({"email_from_address": "from@test.com"})
        set_esign_registry_signing_users_email_content(u"<p>Hello</p>")
        self.request.form["selected_users"] = json.dumps([self.user.getId()])
        view = SigningUsersCsv(self.portal, self.request)
        with patch("imio.esign.browser.views.send_email", return_value=(True, None)):
            view._send_emails()
        messages = IStatusMessage(self.request).show()
        success_msgs = [m for m in messages if m.type == "info"]
        self.assertEqual(len(success_msgs), 1)
        self.assertIn("Emails sent successfully", success_msgs[0].message)

    def test_send_emails_user_with_no_email(self):
        """Shows per-user warning when a selected user has no email address."""
        self.portal.manage_changeProperties({"email_from_address": "from@test.com"})
        set_esign_registry_signing_users_email_content(u"<p>Hello</p>")
        no_email_user = api.user.create(
            email="placeholder@test.com", username="no_email_user", password="password1"  # noqa: S106
        )
        no_email_user.setMemberProperties({"email": ""})
        self.request.form["selected_users"] = json.dumps([no_email_user.getId()])
        view = SigningUsersCsv(self.portal, self.request)
        view._send_emails()
        messages = IStatusMessage(self.request).show()
        no_email_msgs = [m for m in messages if "no email address" in m.message]
        self.assertEqual(len(no_email_msgs), 1)
        self.assertEqual(no_email_msgs[0].type, "warning")

    # --- _render_email_content ---

    def test_render_email_content(self):
        """Renders a TAL template substituting values from user_data."""
        template = u"<p tal:content=\"python: user_data['fullname']\">NAME</p>"
        user_data = {
            "userid": "testuser",
            "email": "test@test.com",
            "lastname": "Smith",
            "firstname": "John",
            "fullname": "John Smith",
        }
        view = SigningUsersCsv(self.portal, self.request)
        result = view._render_email_content(template, user_data)
        self.assertEqual(result, u"<p>John Smith</p>")


class TestItemSessionInfoViewlet(unittest.TestCase):
    """Test ItemSessionInfoViewlet multi-session support."""

    layer = IMIO_ESIGN_INTEGRATION_TESTING

    def setUp(self):
        self.portal = self.layer["portal"]
        self.request = self.portal.REQUEST
        setRoles(self.portal, TEST_USER_ID, ["Manager"])
        at_folder = api.content.create(
            container=self.portal, id="annexes_types", title="Annexes Types",
            type="ContentCategoryConfiguration", exclude_from_nav=True,
        )
        category_group = api.content.create(
            type="ContentCategoryGroup", title="Annexes",
            container=at_folder, id="annexes",
        )
        icon_path = os.path.join(
            os.path.dirname(collective.iconifiedcategory.__file__), "tests", u"ic\xf4ne1.png"
        )
        with open(icon_path, "rb") as fl:
            api.content.create(
                type="ContentCategory", title="To sign",
                container=category_group,
                icon=NamedBlobImage(fl.read(), filename=u"ic\xf4ne1.png"),
                id="to_sign", predefined_title="To be signed",
                to_sign=True, show_preview=False,
            )
        api.user.create(email="user1@sign.com", username="user1", password="password1")
        self.folder = api.content.create(
            container=self.portal, type="Folder",
            id="test_folder", title="Test Folder",
        )
        tests_dir = os.path.dirname(__file__)
        self.annexes = []
        for i in range(2):
            with open(os.path.join(tests_dir, "annex1.pdf"), "rb") as f:
                annex = api.content.create(
                    container=self.folder, type="annex",
                    id="annex{}".format(i), title="Annex {}".format(i),
                    content_category=calculate_category_id(
                        self.portal["annexes_types"]["annexes"]["to_sign"]
                    ),
                    scan_id="0123456000000{:02d}".format(i),
                    file=NamedBlobFile(
                        data=f.read(), filename=u"annex{}.pdf".format(i),
                        contentType="application/pdf",
                    ),
                )
                self.annexes.append(annex)
        self.signers = [("user1", "user1@sign.com", "User 1", "Position 1")]
        for key in list(self.request.form.keys()):
            del self.request.form[key]

    def test_sessions_empty(self):
        """No files in esign annotation → sessions returns empty list."""
        viewlet = ItemSessionInfoViewlet(self.folder, self.request, None, None)
        self.assertEqual(viewlet.sessions, OrderedDict())
        self.assertEqual(viewlet.render(), "")

    def test_sessions_single_session(self):
        """All context files in one session → sessions returns one dict."""
        uids = [a.UID() for a in self.annexes]
        add_files_to_session(self.signers, uids)
        viewlet = ItemSessionInfoViewlet(self.folder, self.request, None, None)
        sessions = viewlet.sessions
        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions.keys(), [0])
        self.assertEqual(len(sessions[0]["files"]), len(uids))

    def test_sessions_multiple_sessions(self):
        """Files in two sessions (different discriminators) → sessions returns two dicts."""
        add_files_to_session(self.signers, [self.annexes[0].UID()], discriminators=("a",))
        add_files_to_session(self.signers, [self.annexes[1].UID()], discriminators=("b",))
        viewlet = ItemSessionInfoViewlet(self.folder, self.request, None, None)
        sessions = viewlet.sessions
        self.assertEqual(len(sessions), 2)
        session_ids = sessions.keys()
        self.assertEqual(session_ids, [0, 1])


class TestSessionsListingView(_BaseSessionViewTest):
    """Test SessionsListingView browser view."""

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
