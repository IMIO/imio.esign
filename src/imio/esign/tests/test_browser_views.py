# -*- coding: utf-8 -*-
"""Browser views tests for this package."""
from datetime import datetime
from datetime import timedelta
from imio.esign.browser.views import DownloadFileView
from imio.esign.testing import IMIO_ESIGN_FUNCTIONAL_TESTING
from imio.pyutils.utils import shortuid_encode_id
from plone import api
from plone.app.testing import logout
from plone.app.testing import setRoles
from plone.app.testing import TEST_USER_ID
from plone.namedfile.file import NamedBlobFile
from plone.namedfile.file import NamedBlobImage
from plone.testing import z2

import collective.iconifiedcategory
import os
import time
import transaction
import unittest


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
