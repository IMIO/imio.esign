# -*- coding: utf-8 -*-
"""utils tests for this package."""
from collective.iconifiedcategory.utils import calculate_category_id
from datetime import date
from datetime import timedelta
from imio.esign.config import get_registry_max_session_size
from imio.esign.config import set_registry_max_session_size
from imio.esign.testing import IMIO_ESIGN_INTEGRATION_TESTING
from imio.esign.utils import add_files_to_session
from imio.esign.utils import create_external_session
from imio.esign.utils import get_file_download_url
from imio.esign.utils import get_filesize
from imio.esign.utils import get_max_download_date
from imio.esign.utils import get_session_annotation
from imio.esign.utils import get_session_info
from imio.esign.utils import get_suid_from_uuid
from imio.esign.utils import remove_context_from_session
from imio.esign.utils import remove_files_from_session
from imio.esign.utils import remove_session
from imio.helpers.content import uuidToObject
from imio.pyutils.utils import shortuid_decode_id
from mock import Mock
from mock import patch
from plone import api
from plone.app.testing import setRoles
from plone.app.testing import TEST_USER_ID
from plone.namedfile.file import NamedBlobFile
from plone.namedfile.file import NamedBlobImage
from zope.annotation import IAnnotations

import collective.iconifiedcategory
import json
import os
import unittest


class TestUtils(unittest.TestCase):

    layer = IMIO_ESIGN_INTEGRATION_TESTING

    def setUp(self):
        self.portal = self.layer["portal"]
        setRoles(self.portal, TEST_USER_ID, ["Manager"])
        # add some users
        api.user.create(email="user1@sign.com", username="user1", password="password1")
        api.user.create(email="user2@sign.com", username="user2", password="password2")
        # add content category configuration
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
                # confidential=True,
                # to_print=True,
                to_sign=True,
                # signed=True,
                # publishable=True,
                # only_pdf=True,
                show_preview=False,
            )
        # add annexes
        self.folders = []
        for f in range(2):
            folder = api.content.create(
                container=self.portal,
                id="folder{}".format(f),
                title="Folder {}".format(f),
                type="Folder",
            )
            self.folders.append(folder)
        tests_dir = os.path.dirname(__file__)
        pdf_files = ["annex1.pdf", "annex2.pdf"]
        self.uids = []
        for i in range(12):
            pdf_file = pdf_files[i % len(pdf_files)]
            container = self.folders[i % len(self.folders)]
            with open(os.path.join(tests_dir, pdf_file), "rb") as f:
                annex = api.content.create(
                    container=container,
                    type="annex",
                    id="annex{}".format(i),
                    title="Annex {}".format(i),
                    content_category=calculate_category_id(self.portal["annexes_types"]["annexes"]["to_sign"]),
                    scan_id="0123456000000{:02d}".format(i),
                    file=NamedBlobFile(data=f.read(), filename=u"annex{}.pdf".format(i), contentType="application/pdf"),
                )
                self.uids.append(annex.UID())

    def test_add_remove_files_to_session(self):
        root_annot = IAnnotations(self.portal)
        self.assertNotIn("imio.esign", root_annot)
        signers = [
            ("user1", "user1@sign.com", "User 1", "Position 1"),
            ("user2", "user2@sign.com", "User 2", "Position 2"),
        ]

        # add files, no session_id, no discriminator
        sid, session = add_files_to_session(signers, (self.uids[0],), title="my title", watchers=("stalker@sign.com",))
        self.assertEqual(sid, 0)
        annot = root_annot["imio.esign"]
        self.assertEqual(annot["numbering"], 1)
        self.assertEqual(len(annot["sessions"]), 1)
        self.assertEqual(len(annot["uids"]), 1)
        self.assertIn(self.uids[0], annot["uids"])
        self.assertEqual(len(annot["c_uids"][self.folders[0].UID()]), 1)
        self.assertDictEqual(dict(annot["c_uids"]), {self.folders[0].UID(): [self.uids[0]]})
        self.assertEqual(session["title"], "my title")
        self.assertEqual(session["state"], "draft")
        self.assertEqual(session["seal"], None)
        self.assertEqual(session["acroform"], True)
        self.assertIsNone(session["sign_url"])
        self.assertEqual(session["client_id"], "0123456")
        self.assertEqual(len(session["watchers"]), 1)
        self.assertEqual(len(session["files"]), 1)
        self.assertListEqual(
            list(session["files"]),
            [
                {
                    "context_uid": self.folders[0].UID(),
                    "scan_id": "012345600000000",
                    "title": "Annex 0",
                    "uid": self.uids[0],
                    "status": "",
                    "filename": u"annex0.pdf",
                }
            ],
        )
        self.assertEqual(len(session["signers"]), 2)
        self.assertEqual(session["size"], 6968)  # annex1.pdf

        # add files, no session_id => same session reused
        signers[1] = ("user2", "user2@sign.com", "User 2", "Position 2b")  # changed position => not discriminant
        sid, session = add_files_to_session(signers, (self.uids[1],))
        self.assertEqual(sid, 0)
        self.assertEqual(annot["numbering"], 1)
        self.assertEqual(len(annot["sessions"]), 1)
        self.assertEqual(len(annot["uids"]), 2)
        self.assertIn(self.uids[1], annot["uids"])
        self.assertEqual(len(annot["c_uids"]), 2)
        self.assertIn(self.folders[1].UID(), annot["c_uids"])
        self.assertEqual(len(session["files"]), 2)
        self.assertEqual(len(annot["c_uids"][self.folders[1].UID()]), 1)
        self.assertEqual(session["size"], 6968 + 7014)  # annex1 + annex2

        # add files, no session_id, new discriminations => new session
        sid, session = add_files_to_session(signers, (self.uids[2],), discriminators=("council1",))
        self.assertEqual(sid, 1)
        self.assertEqual(annot["numbering"], 2)
        self.assertEqual(len(annot["sessions"]), 2)
        self.assertEqual(len(annot["uids"]), 3)
        self.assertIn(self.uids[2], annot["uids"])
        self.assertEqual(len(session["files"]), 1)
        self.assertEqual(len(session["watchers"]), 0)

        # add files, no session_id, same discriminations => same session
        sid, session = add_files_to_session(signers, (self.uids[3],), discriminators=("council1",))
        self.assertEqual(sid, 1)
        self.assertEqual(annot["numbering"], 2)
        self.assertEqual(len(annot["sessions"]), 2)
        self.assertEqual(len(annot["uids"]), 4)
        self.assertIn(self.uids[3], annot["uids"])
        self.assertEqual(len(session["files"]), 2)

        # add files, no session_id, other discriminations => other session
        sid, session = add_files_to_session(signers, (self.uids[4],), discriminators=("council2",))
        self.assertEqual(sid, 2)

        # add files, session_id, other discriminations => reused session
        sid, session = add_files_to_session(signers, (self.uids[5],), session_id=0, discriminators=("council3",))
        self.assertEqual(sid, 0)

        # add files, session_id unfound, other discriminations => new session
        sid, session = add_files_to_session(signers, (self.uids[6],), session_id=999, discriminators=("council3",))
        self.assertEqual(sid, 3)

        # add files, no session_id, different signers => new session
        sid, session = add_files_to_session([signers[0]], (self.uids[7],))
        self.assertEqual(sid, 4)

        # add files, no session_id, different seal => new session
        sid, session = add_files_to_session(signers, (self.uids[8],), seal="seal1")
        self.assertEqual(sid, 5)

        # add files, no session_id, same seal, different acroform => new session
        sid, session = add_files_to_session(signers, (self.uids[9],), acroform=False)
        self.assertEqual(sid, 6)
        self.assertEqual(len(annot["uids"]), 10)
        self.assertEqual(len(annot["c_uids"]), 2)
        self.assertEqual(len(annot["c_uids"][self.folders[0].UID()]), 5)
        self.assertEqual(len(annot["c_uids"][self.folders[1].UID()]), 5)
        self.assertEqual(len(annot["sessions"]), 7)

        # add files, no session_id, no signers => new session
        sid, session = add_files_to_session([], (self.uids[10],), seal="seal2")
        self.assertEqual(sid, 7)
        self.assertEqual(len(annot["sessions"]), 8)
        self.assertEqual(session["signers"], [])
        self.assertEqual(session["seal"], "seal2")

        # add files, no session_id, same seal, different states => new session
        session["state"] = "sent"
        sid, session = add_files_to_session([], (self.uids[11],), seal="seal2")
        self.assertEqual(sid, 8)
        self.assertEqual(len(annot["sessions"]), 9)

        # now we can start to remove
        remove_files_from_session((self.uids[0], self.uids[1]))  # 2 of 3 session files
        self.assertEqual(len(annot["uids"]), 10)
        self.assertEqual(len(annot["sessions"][0]["files"]), 1)
        self.assertEqual(annot["sessions"][0]["size"], 7014)  # only uid[5] (annex2) remains
        self.assertEqual(len(annot["c_uids"][self.folders[0].UID()]), 5)
        self.assertEqual(len(annot["c_uids"][self.folders[1].UID()]), 5)
        remove_files_from_session((self.uids[5],))  # no more session files, session removed
        self.assertEqual(len(annot["uids"]), 9)
        self.assertEqual(len(annot["sessions"]), 8)
        self.assertNotIn(0, annot["sessions"])
        remove_files_from_session((self.uids[2], self.uids[3]))  # all session files, session removed
        self.assertEqual(len(annot["uids"]), 7)
        self.assertEqual(len(annot["sessions"]), 7)
        self.assertNotIn(1, annot["sessions"])
        remove_files_from_session((self.uids[4],))
        remove_files_from_session((self.uids[6],))
        remove_files_from_session((self.uids[7],))
        remove_files_from_session((self.uids[8],))
        remove_files_from_session((self.uids[9],))
        remove_files_from_session((self.uids[10],))
        remove_files_from_session((self.uids[11],))
        self.assertEqual(len(annot["uids"]), 0)
        self.assertEqual(len(annot["c_uids"]), 0)
        self.assertEqual(len(annot["sessions"]), 0)

    def test_get_filesize(self):
        """Test get_filesize returns the correct file size."""
        # even index => annex1.pdf (6968 bytes)
        self.assertEqual(get_filesize(self.uids[0]), 6968)
        # odd index => annex2.pdf (7014 bytes)
        self.assertEqual(get_filesize(self.uids[1]), 7014)
        # invalid UID returns 0
        self.assertEqual(get_filesize("nonexistent_uid"), 0)
        # check size get robustness
        annex = uuidToObject(uuid=self.uids[0], unrestricted=True)
        self.assertEqual(annex.content_category, "plone-annexes_types_-_annexes_-_to_sign")
        folder = annex.__parent__
        self.assertEqual(folder.categorized_elements[self.uids[0]]["filesize"], 6968)
        folder.categorized_elements[self.uids[0]]["filesize"] = 1111
        self.assertEqual(get_filesize(self.uids[0]), 1111)
        del folder.categorized_elements[self.uids[0]]["filesize"]
        self.assertEqual(get_filesize(self.uids[0]), 6968)
        del folder.categorized_elements[self.uids[0]]
        self.assertEqual(get_filesize(self.uids[0]), 6968)
        delattr(folder, "categorized_elements")
        self.assertEqual(get_filesize(self.uids[0]), 6968)

    def test_session_size_discrimination(self):
        """Test that sessions are split when they would exceed max_session_size."""
        signers = [
            ("user1", "user1@sign.com", "User 1", "Position 1"),
        ]

        # add one file to create a session (annex1.pdf = 6968 bytes)
        sid, session = add_files_to_session(signers, (self.uids[0],))
        self.assertEqual(sid, 0)
        self.assertEqual(session["size"], 6968)

        # set session size just under the 1 MB limit so adding another file exceeds it
        session["size"] = 1 * 1024**2 - 1  # 1 MB - 1 byte
        previous_max = get_registry_max_session_size()
        self.addCleanup(set_registry_max_session_size, previous_max)
        set_registry_max_session_size(1)

        # adding a file (~7KB) would exceed 1 MB => new session created
        sid2, session2 = add_files_to_session(signers, (self.uids[1],))
        self.assertEqual(sid2, 1)
        self.assertIsNot(session2, session)
        self.assertEqual(session2["size"], 7014)

        # with enough room, files go to the same session
        sid3, session3 = add_files_to_session(signers, (self.uids[2],))
        self.assertEqual(sid3, 1)
        self.assertIs(session3, session2)
        self.assertEqual(session3["size"], 7014 + 6968)

    def test_add_files_with_duplicate_filenames(self):
        """Test that files with duplicate filenames are renamed with suffix."""
        annot = get_session_annotation()
        self.assertEqual(len(annot["sessions"]), 0)

        signers = [
            ("user1", "user1@sign.com", "User 1", "Position 1"),
        ]

        for i in range(3):
            annex = api.content.get(UID=self.uids[i])
            annex.file.filename = u"same_filename.pdf"
            # annex.reindexObject()

        sid, session = add_files_to_session(signers, (self.uids[0],))
        self.assertEqual(len(session["files"]), 1)
        self.assertEqual(session["files"][0]["filename"], "same_filename.pdf")
        sid, session = add_files_to_session(signers, (self.uids[1],), session_id=sid)
        self.assertEqual(len(session["files"]), 2)
        self.assertIn("same_filename-1.pdf", [f["filename"] for f in session["files"]])

        sid, session = add_files_to_session(signers, (self.uids[2],), session_id=sid)
        self.assertEqual(len(session["files"]), 3)
        filenames = [f["filename"] for f in session["files"]]
        self.assertIn("same_filename.pdf", filenames)
        self.assertIn("same_filename-1.pdf", filenames)
        self.assertIn("same_filename-2.pdf", filenames)

    def test_remove_context_from_session(self):
        """Test removing a context from a session."""
        annot = get_session_annotation()
        self.assertEqual(len(annot["sessions"]), 0)
        signers = [
            ("user1", "user1@sign.com", "User 1", "Position 1"),
            ("user2", "user2@sign.com", "User 2", "Position 2"),
        ]
        sid, session = add_files_to_session(signers, (self.uids[0], self.uids[1], self.uids[2], self.uids[3]))
        self.assertEqual(len(annot["uids"]), 4)
        self.assertEqual(len(annot["c_uids"]), 2)
        self.assertEqual(len(annot["sessions"]), 1)
        remove_context_from_session((self.folders[0].UID(),))
        self.assertEqual(len(annot["uids"]), 2)
        self.assertEqual(len(annot["c_uids"]), 1)
        self.assertEqual(len(annot["sessions"]), 1)
        remove_context_from_session((self.folders[1].UID(),))
        self.assertEqual(len(annot["uids"]), 0)
        self.assertEqual(len(annot["c_uids"]), 0)
        self.assertEqual(len(annot["sessions"]), 0)

    def test_remove_session(self):
        """Test removing a session."""
        annot = get_session_annotation()
        self.assertEqual(len(annot["sessions"]), 0)
        signers = [
            ("user1", "user1@sign.com", "User 1", "Position 1"),
            ("user2", "user2@sign.com", "User 2", "Position 2"),
        ]
        sid, session = add_files_to_session(signers, (self.uids[0], self.uids[1]))
        self.assertEqual(sid, 0)
        sid, session = add_files_to_session(signers, (self.uids[2], self.uids[3]), seal="seal1")
        self.assertEqual(sid, 1)
        remove_session(0)  # remove first session
        self.assertEqual(len(annot["uids"]), 2)
        self.assertEqual(len(annot["c_uids"]), 2)
        self.assertEqual(len(annot["sessions"]), 1)

    def test_get_session_info(self):
        """Test getting info about a given session id."""
        annot = get_session_annotation()
        self.assertEqual(len(annot["sessions"]), 0)
        self.assertIsNone(get_session_info(0))
        self.assertIsNone(get_session_info(1))
        self.assertIsNone(get_session_info(2))
        signers = [
            ("user1", "user1@sign.com", "User 1", "Position 1"),
            ("user2", "user2@sign.com", "User 2", "Position 2"),
        ]
        sid, session = add_files_to_session(signers, (self.uids[0], self.uids[1]))
        self.assertEqual(get_session_info(sid), session)

    def test_get_file_download_url(self):
        """Test generating file download URL from UID."""
        uid = "f40682caafc045b4b81973bd82ea9ab6"
        # Test error when no root_url is configured
        with self.assertRaises(Exception) as cm:
            get_file_download_url(uid)
        self.assertIn("No root URL provided", str(cm.exception))

        api.portal.set_registry_record("imio.esign.file_url", "https://downloads.files.com")

        result = get_file_download_url(uid)
        self.assertEqual(result, ("https://downloads.files.com/Rzgwy-9BVG9-viEts-5GBkn-Rm",
                                  "Rzgwy-9BVG9-viEts-5GBkn-Rm"))

        custom_url = "https://custom.domain.org/"
        result = get_file_download_url(uid, root_url=custom_url)
        self.assertEqual(result[0], "https://custom.domain.org/Rzgwy-9BVG9-viEts-5GBkn-Rm")

        # Test with another UID to verify encoding works
        uid2 = self.uids[0]
        result2 = get_file_download_url(uid2)
        self.assertTrue(result2[0].startswith("https://downloads.files.com/"))
        self.assertEqual(shortuid_decode_id(result2[1], separator="-"), uid2)  # correctly decoded

        # Test with pre-computed short_uid parameter
        result3 = get_file_download_url(None, short_uid="MyCustom-Short-UID")
        self.assertEqual(result3, ("https://downloads.files.com/MyCustom-Short-UID", "MyCustom-Short-UID"))

    def test_get_max_download_date(self):
        annex = self.folders[0]
        mod_date = annex.modified().asdatetime().date()
        self.assertEqual(get_max_download_date(annex), mod_date + timedelta(days=90))
        self.assertEqual(get_max_download_date(annex, timedelta(days=0)), mod_date)
        today = date.today()
        self.assertEqual(get_max_download_date(None, timedelta(days=0), today), today)

    def test_create_external_session_not_found(self):
        """Returns _session_not_found_ for a non-existent session id."""
        result = create_external_session(9999)
        self.assertEqual(result, "_session_not_found_")

    def test_create_external_session_no_seal_email(self):
        """Returns _no_seal_email_ when session requires a seal but no email configured."""
        sid, _session = add_files_to_session([], (self.uids[0],), seal="SEAL")
        # seal_email defaults to "" (falsy) — no registry setup needed
        result = create_external_session(sid, esign_root_url="http://test.example.com")
        self.assertEqual(result, "_no_seal_email_")

    def test_create_external_session_no_seal_code(self):
        """Returns _no_seal_code_ when seal email is set but seal code is missing."""
        sid, _session = add_files_to_session([], (self.uids[0],), seal="SEAL")
        api.portal.set_registry_record("imio.esign.seal_email", u"seal@example.com")
        self.addCleanup(api.portal.set_registry_record, "imio.esign.seal_email", u"")
        # seal_code defaults to "" (falsy)
        result = create_external_session(sid, esign_root_url="http://test.example.com")
        self.assertEqual(result, "_no_seal_code_")

    def test_create_external_session_error_response(self):
        """Returns response object and leaves session state unchanged on non-200."""
        signers = [("user1", "user1@sign.com", "User 1", "Position 1")]
        sid, session = add_files_to_session(signers, (self.uids[0],))
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        with patch("imio.esign.utils.requests.post", return_value=mock_response):
            with patch("imio.esign.utils.get_auth_token", return_value="test-token"):
                result = create_external_session(sid, esign_root_url="http://test.example.com")
        self.assertIs(result, mock_response)
        self.assertEqual(session["state"], "draft")

    def test_create_external_session_sign_payload(self):
        """Returns response object, sets session state to 'sent', and signData contains signer email."""
        signers = [("user1", "user1@sign.com", "User 1", "Position 1")]
        sid, session = add_files_to_session(signers, (self.uids[0],))
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = '{"message": "OK"}'
        with patch("imio.esign.utils.requests.post", return_value=mock_response) as mock_post:
            with patch("imio.esign.utils.get_auth_token", return_value="test-token"):
                result = create_external_session(sid, esign_root_url="http://test.example.com")
        self.assertIs(result, mock_response)
        self.assertEqual(session["state"], "sent")
        payload = json.loads(mock_post.call_args[1]["data"]["data"])
        self.assertEqual(
            payload,
            {
                u"commonData": {
                    u"imioAppSessionId": u"012345600000",
                    u"vatNumber": None,
                    u"endpointUrl": u"http://nohost/plone/@external_session_feedback",
                    u"sessionName": u"Session 0",
                    u"documentData": [
                        {
                            u"uniqueCode": u"012345600000000__{}".format(self.uids[0]),
                            u"docUuid": get_suid_from_uuid(self.uids[0]),
                            u"filename": u"annex0.pdf",
                        }
                    ],
                },
                u"signData": {u"acroform": True, u"users": [u"user1@sign.com"]},
            },
        )

    def test_create_external_session_seal_payload(self):
        """Seal-only session: sealData contains seal email and code; no signData."""
        sid, _session = add_files_to_session([], (self.uids[0],), seal="SEAL")
        api.portal.set_registry_record("imio.esign.seal_email", u"seal@example.com")
        api.portal.set_registry_record("imio.esign.seal_code", u"PADES_SEAL")
        self.addCleanup(api.portal.set_registry_record, "imio.esign.seal_email", u"")
        self.addCleanup(api.portal.set_registry_record, "imio.esign.seal_code", u"")
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = '{"message": "OK"}'
        with patch("imio.esign.utils.requests.post", return_value=mock_response) as mock_post:
            with patch("imio.esign.utils.get_auth_token", return_value="test-token"):
                create_external_session(sid, esign_root_url="http://test.example.com")
        payload = json.loads(mock_post.call_args[1]["data"]["data"])
        self.assertEqual(
            payload,
            {
                u"commonData": {
                    u"imioAppSessionId": u"012345600000",
                    u"vatNumber": None,
                    u"endpointUrl": u"http://nohost/plone/@external_session_feedback",
                    u"sessionName": u"Session 0",
                    u"documentData": [
                        {
                            u"uniqueCode": u"012345600000000__{}".format(self.uids[0]),
                            u"docUuid": get_suid_from_uuid(self.uids[0]),
                            u"filename": u"annex0.pdf",
                        }
                    ],
                },
                u"sealData": {
                    u"sealCode": u"PADES_SEAL",
                    u"acroform": True,
                    u"users": [u"seal@example.com"],
                    u"watchers": [],
                },
            },
        )

    def test_create_external_session_both_payload(self):
        """Session with signers and seal: both signData and sealData are present."""
        signers = [("user1", "user1@sign.com", "User 1", "Position 1")]
        sid, _session = add_files_to_session(signers, (self.uids[0],), seal="SEAL")
        api.portal.set_registry_record("imio.esign.seal_email", u"seal@example.com")
        api.portal.set_registry_record("imio.esign.seal_code", u"PADES_SEAL")
        self.addCleanup(api.portal.set_registry_record, "imio.esign.seal_email", u"")
        self.addCleanup(api.portal.set_registry_record, "imio.esign.seal_code", u"")
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = '{"message": "OK"}'
        with patch("imio.esign.utils.requests.post", return_value=mock_response) as mock_post:
            with patch("imio.esign.utils.get_auth_token", return_value="test-token"):
                create_external_session(sid, esign_root_url="http://test.example.com")
        payload = json.loads(mock_post.call_args[1]["data"]["data"])
        self.assertEqual(
            payload,
            {
                u"signData": {u"acroform": True, u"users": [u"user1@sign.com"]},
                u"commonData": {
                    u"imioAppSessionId": u"012345600000",
                    u"vatNumber": None,
                    u"endpointUrl": u"http://nohost/plone/@external_session_feedback",
                    u"sessionName": u"Session 0",
                    u"documentData": [
                        {
                            u"uniqueCode": u"012345600000000__{}".format(self.uids[0]),
                            u"docUuid": get_suid_from_uuid(self.uids[0]),
                            u"filename": u"annex0.pdf",
                        }
                    ],
                },
                u"sealData": {
                    u"sealCode": u"PADES_SEAL",
                    u"acroform": True,
                    u"users": [u"seal@example.com"],
                    u"watchers": [],
                },
            },
        )


# example of annotation content
"""
{
    "numbering": 1,
    "uids": {"3c0528c0ad364641be8b9cbaedbf6620": 0},
    "c_uids": {"f66b3da2d2e947fd81ab65e3e36c039d": ["3c0528c0ad364641be8b9cbaedbf6620"]},
    "sessions": {
        0: {
            "acroform": True,
            "cliend_id": "0123456",
            "discriminators": (),
            "files": [
                {
                    "context_uid": "f66b3da2d2e947fd81ab65e3e36c039d",
                    "scan_id": "012345600000000",
                    "title": u"Annex 0",
                    "uid": "3c0528c0ad364641be8b9cbaedbf6620",
                    "filename": u"annex0.pdf",
                }
            ],
            "last_update": datetime.datetime(2025, 8, 13, 13, 22, 41, 107895),
            "returns": []
            "seal": None,
            "sign_id": None,
            "sign_url": None,
            "signers": [
                {
                    "status": "",
                    "userid": "user1",
                    "email": "user1@sign.com",
                    "fullname": "User 1",
                    "position": "Position 1",
                },
                {
                    "status": "",
                    "userid": "user2",
                    "email": "user2@sign.com",
                    "fullname": "User 2",
                    "position": "Position 2",
                },
            ],
            "state": "draft",
            "title": "my title",
        }
    },
}
"""
