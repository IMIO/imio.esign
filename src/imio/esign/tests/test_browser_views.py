# -*- coding: utf-8 -*-
"""Browser views tests for this package."""
from AccessControl import Unauthorized
from collective.iconifiedcategory.utils import calculate_category_id
from datetime import datetime
from datetime import timedelta
from imio.esign.browser.views import DownloadFileView
from imio.esign.browser.views import ExternalSessionCreateView
from imio.esign.browser.views import SessionDeleteView
from imio.esign.testing import IMIO_ESIGN_FUNCTIONAL_TESTING
from imio.esign.testing import IMIO_ESIGN_INTEGRATION_TESTING
from imio.esign.utils import add_files_to_session
from imio.esign.utils import get_session_annotation
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
import os
import transaction
import unittest


class _BaseSessionViewTest(unittest.TestCase):
    """Base test class with shared setUp for session view tests."""

    layer = IMIO_ESIGN_INTEGRATION_TESTING

    def setUp(self):
        self.portal = self.layer["portal"]
        self.request = self.layer["request"]
        setRoles(self.portal, TEST_USER_ID, ["Manager"])

        # Create user for signing
        api.user.create(email="user1@sign.com", username="user1", password="password1")

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
