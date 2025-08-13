# -*- coding: utf-8 -*-
"""utils tests for this package."""
from imio.esign.testing import IMIO_ESIGN_INTEGRATION_TESTING  # noqa: E501
from imio.esign.utils import add_files_to_session
from plone import api
from plone.app.testing import setRoles
from plone.app.testing import TEST_USER_ID
from plone.namedfile.file import NamedBlobFile
from plone.namedfile.file import NamedBlobImage
from zope.annotation import IAnnotations

import collective.iconifiedcategory
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
            title=u"Annexes Types",
            type="ContentCategoryConfiguration",
            exclude_from_nav=True,
        )
        category_group = api.content.create(
            type="ContentCategoryGroup",
            title=u"Annexes",
            container=at_folder,
            id="annexes",
        )
        icon_path = os.path.join(os.path.dirname(collective.iconifiedcategory.__file__), "tests", "icône1.png")
        with open(icon_path, "rb") as fl:
            api.content.create(
                type="ContentCategory",
                title=u"To sign",
                container=category_group,
                icon=NamedBlobImage(fl.read(), filename=u"icône1.png"),
                id="to_sign",
                predefined_title=u"To be signed",
                # confidential=True,
                # to_print=True,
                to_sign=True,
                # signed=True,
                # publishable=True,
                # only_pdf=True,
                show_preview=False,
            )
        # add annexes
        tests_dir = os.path.dirname(__file__)
        with open(os.path.join(tests_dir, "annex1.pdf"), "rb") as f:
            annex1 = api.content.create(
                container=self.portal,
                type="annex",
                id="annex1",
                title="Annex 1",
                content_category="to_sign",
                scan_id="012345600000001",
                file=NamedBlobFile(data=f.read(), filename=u"annex1.pdf", contentType="application/pdf"),
            )
            self.uid1 = annex1.UID()
        with open(os.path.join(tests_dir, "annex2.pdf"), "rb") as f:
            annex2 = api.content.create(
                container=self.portal,
                type="annex",
                id="annex2",
                title="Annex 2",
                content_category="to_sign",
                scan_id="012345600000002",
                file=NamedBlobFile(data=f.read(), filename=u"annex2.pdf", contentType="application/pdf"),
            )
            self.uid2 = annex2.UID()

    def test_add_files_to_session(self):
        root_annot = IAnnotations(self.portal)
        self.assertNotIn("imio.esign", root_annot)
        signers = [("user1", "user1@sign.com"), ("user2", "user2@sign.com")]
        # no files and no session_id
        add_files_to_session(signers, files_uids=(), session_id=None, title="my title")
        self.assertIn("imio.esign", root_annot)
        annot = root_annot["imio.esign"]
        self.assertEqual(annot["numbering"], 1)
        self.assertEqual(len(annot["sessions"]), 1)
        self.assertEqual(len(annot["uids"]), 0)  # no files
        session = annot["sessions"][0]
        self.assertEqual(session["title"], "my title")
        self.assertEqual(session["state"], "draft")
        self.assertEqual(session["seal"], False)
        self.assertEqual(len(session["files"]), 0)
        self.assertEqual(len(session["signers"]), 2)
        # add files, no session_id
        add_files_to_session(signers, files_uids=(self.uid1,), session_id=None, title="my title")
        self.assertEqual(annot["numbering"], 1)
        self.assertEqual(len(annot["sessions"]), 1)
        self.assertEqual(len(annot["uids"]), 1)
        self.assertIn(self.uid1, annot["uids"])
        session = annot["sessions"][0]
        self.assertEqual(len(session["files"]), 1)
        """
        {
            "numbering": 1,
            "uids": {"3bad658001574309abfa4127868f770a": 0},
            "sessions": {
                0: {
                    "files": [
                        {
                            "scan_id": "012345600000001",
                            "title": u"Annex 1",
                            "uid": "3bad658001574309abfa4127868f770a",
                            "filename": u"annex1.pdf",
                        }
                    ],
                    "title": "my title",
                    "signers": [
                        {"status": "", "userid": "user1", "email": "user1@sign.com"},
                        {"status": "", "userid": "user2", "email": "user2@sign.com"},
                    ],
                    "last_update": datetime.datetime(2025, 8, 13, 10, 44, 1, 419579),
                    "state": "draft",
                    "seal": False,
                }
            },
        }
        """
