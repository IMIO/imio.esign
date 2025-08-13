# -*- coding: utf-8 -*-
"""utils tests for this package."""
from imio.esign.testing import IMIO_ESIGN_INTEGRATION_TESTING  # noqa: E501
from imio.esign.utils import add_files_to_session
from imio.esign.utils import get_session_annotation
from imio.esign.utils import remove_context_from_session
from imio.esign.utils import remove_files_from_session
from imio.esign.utils import remove_session
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
        for i in range(9):
            pdf_file = pdf_files[i % len(pdf_files)]
            container = self.folders[i % len(self.folders)]
            with open(os.path.join(tests_dir, pdf_file), "rb") as f:
                annex = api.content.create(
                    container=container,
                    type="annex",
                    id="annex{}".format(i),
                    title="Annex {}".format(i),
                    content_category="to_sign",
                    scan_id="0123456000000{:02d}".format(i),
                    file=NamedBlobFile(data=f.read(), filename=u"annex{}.pdf".format(i), contentType="application/pdf"),
                )
                self.uids.append(annex.UID())

    def test_add_remove_files_to_session(self):
        root_annot = IAnnotations(self.portal)
        self.assertNotIn("imio.esign", root_annot)
        signers = [("user1", "user1@sign.com"), ("user2", "user2@sign.com")]
        # add files, no session_id, no discriminator
        sid, session = add_files_to_session(signers, (self.uids[0],), title="my title")
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
        self.assertEqual(session["seal"], False)
        self.assertEqual(len(session["files"]), 1)
        self.assertListEqual(
            list(session["files"]),
            [
                {
                    "context_uid": self.folders[0].UID(),
                    "scan_id": "012345600000000",
                    "title": "Annex 0",
                    "uid": self.uids[0],
                    "filename": "annex0.pdf",
                }
            ],
        )
        self.assertEqual(len(session["signers"]), 2)
        # add files, no session_id => same session reused
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
        # add files, no session_id, new discriminations => new session
        sid, session = add_files_to_session(signers, (self.uids[2],), discriminators=("council1",))
        self.assertEqual(sid, 1)
        self.assertEqual(annot["numbering"], 2)
        self.assertEqual(len(annot["sessions"]), 2)
        self.assertEqual(len(annot["uids"]), 3)
        self.assertIn(self.uids[2], annot["uids"])
        self.assertEqual(len(session["files"]), 1)
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
        sid, session = add_files_to_session(signers, (self.uids[8],), seal=True)
        self.assertEqual(sid, 5)

        self.assertEqual(len(annot["uids"]), 9)
        self.assertEqual(len(annot["c_uids"]), 2)
        self.assertEqual(len(annot["c_uids"][self.folders[0].UID()]), 5)
        self.assertEqual(len(annot["c_uids"][self.folders[1].UID()]), 4)
        self.assertEqual(len(annot["sessions"]), 6)

        # now we can start to remove
        remove_files_from_session((self.uids[0], self.uids[1]))  # 2 of 3 session files
        self.assertEqual(len(annot["uids"]), 7)
        self.assertEqual(len(annot["sessions"][0]["files"]), 1)
        self.assertEqual(len(annot["c_uids"][self.folders[0].UID()]), 4)
        self.assertEqual(len(annot["c_uids"][self.folders[1].UID()]), 3)
        remove_files_from_session((self.uids[5],))  # no more session files, session removed
        self.assertEqual(len(annot["uids"]), 6)
        self.assertEqual(len(annot["sessions"]), 5)
        self.assertNotIn(0, annot["sessions"])
        remove_files_from_session((self.uids[2], self.uids[3]))  # all session files, session removed
        self.assertEqual(len(annot["uids"]), 4)
        self.assertEqual(len(annot["sessions"]), 4)
        self.assertNotIn(1, annot["sessions"])
        remove_files_from_session((self.uids[4],))
        remove_files_from_session((self.uids[6],))
        remove_files_from_session((self.uids[7],))
        remove_files_from_session((self.uids[8],))
        self.assertEqual(len(annot["uids"]), 0)
        self.assertEqual(len(annot["c_uids"]), 0)
        self.assertEqual(len(annot["sessions"]), 0)

    def test_remove_context_from_session(self):
        """Test removing a context from a session."""
        annot = get_session_annotation()
        self.assertEqual(len(annot["sessions"]), 0)
        signers = [("user1", "user1@sign.com"), ("user2", "user2@sign.com")]
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
        signers = [("user1", "user1@sign.com"), ("user2", "user2@sign.com")]
        sid, session = add_files_to_session(signers, (self.uids[0], self.uids[1]))
        self.assertEqual(sid, 0)
        sid, session = add_files_to_session(signers, (self.uids[2], self.uids[3]), seal=True)
        self.assertEqual(sid, 1)
        import pdbp

        pdbp.set_trace()
        remove_session(0)  # remove first session
        self.assertEqual(len(annot["uids"]), 2)
        self.assertEqual(len(annot["c_uids"]), 2)
        self.assertEqual(len(annot["sessions"]), 1)


# example of annotation content
"""
{
    "numbering": 1,
    "uids": {"3c0528c0ad364641be8b9cbaedbf6620": 0},
    "c_uids": {"f66b3da2d2e947fd81ab65e3e36c039d": ["3c0528c0ad364641be8b9cbaedbf6620"]},
    "sessions": {
        0: {
            "files": [
                {
                    "context_uid": "f66b3da2d2e947fd81ab65e3e36c039d",
                    "scan_id": "012345600000000",
                    "title": u"Annex 0",
                    "uid": "3c0528c0ad364641be8b9cbaedbf6620",
                    "filename": u"annex0.pdf",
                }
            ],
            "discriminators": (),
            "title": "my title",
            "signers": [
                {"status": "", "userid": "user1", "email": "user1@sign.com"},
                {"status": "", "userid": "user2", "email": "user2@sign.com"},
            ],
            "last_update": datetime.datetime(2025, 8, 13, 13, 22, 41, 107895),
            "state": "draft",
            "seal": False,
        }
    },
}
"""
