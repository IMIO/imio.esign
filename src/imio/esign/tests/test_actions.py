# -*- coding: utf-8 -*-
"""actions tests for this package."""
from collective.iconifiedcategory.utils import calculate_category_id
from imio.esign.testing import IMIO_ESIGN_INTEGRATION_TESTING
from imio.esign.utils import add_files_to_session
from imio.esign.utils import get_session_annotation
from plone import api
from plone.app.testing import setRoles
from plone.app.testing import TEST_USER_ID
from plone.namedfile.file import NamedBlobFile
from plone.namedfile.file import NamedBlobImage
from Products.statusmessages.interfaces import IStatusMessage
from zope.component import getMultiAdapter

import collective.iconifiedcategory
import os
import unittest


class BaseRemoveFromSession(unittest.TestCase):
    """Base class to centralize setUp."""

    layer = IMIO_ESIGN_INTEGRATION_TESTING

    def setUp(self):
        self.portal = self.layer["portal"]
        self.request = self.portal.REQUEST
        setRoles(self.portal, TEST_USER_ID, ["Manager"])
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
                to_sign=True,
                show_preview=False,
            )
        # add users and annexes
        api.user.create(email="user1@sign.com", username="user1", password="password1")
        self.folder = api.content.create(
            container=self.portal, type="Folder", id="test_folder", title="Test Folder"
        )
        tests_dir = os.path.dirname(__file__)
        self.annexes = []
        for i in range(3):
            with open(os.path.join(tests_dir, "annex1.pdf"), "rb") as f:
                annex = api.content.create(
                    container=self.folder,
                    type="annex",
                    id="annex{}".format(i),
                    title="Annex {}".format(i),
                    content_category=calculate_category_id(self.portal["annexes_types"]["annexes"]["to_sign"]),
                    scan_id="0123456000000{:02d}".format(i),
                    file=NamedBlobFile(data=f.read(), filename=u"annex{}.pdf".format(i), contentType="application/pdf"),
                )
                self.annexes.append(annex)
        self.signers = [("user1", "user1@sign.com", "User 1", "Position 1")]


class TestRemoveItemFromSessionView(BaseRemoveFromSession):
    """Test RemoveItemFromSessionView browser view."""

    def test_available(self):
        """Test available method returns True."""
        view = getMultiAdapter((self.annexes[0], self.request), name="remove-item-from-esign-session")
        self.assertFalse(view.available())
        uids = [a.UID() for a in self.annexes]
        add_files_to_session(self.signers, uids)
        self.assertTrue(view.available())

    def test_index_removes_file_from_session(self):
        """Test index() removes the file from the esign session."""
        annot = get_session_annotation()
        # Add files to a session
        uids = [a.UID() for a in self.annexes]
        add_files_to_session(self.signers, uids)
        self.assertEqual(len(annot["sessions"]), 1)
        self.assertEqual(len(annot["uids"]), 3)
        session = annot["sessions"][0]
        self.assertEqual(len(session["files"]), 3)

        # Remove one file via the view
        view = getMultiAdapter((self.annexes[0], self.request), name="remove-item-from-esign-session")
        view.index()
        # The file should be removed from the session
        self.assertNotIn(uids[0], annot["uids"])
        self.assertEqual(len(annot["uids"]), 2)
        self.assertEqual(len(session["files"]), 2)
        remaining_uids = [f["uid"] for f in session["files"]]
        self.assertNotIn(uids[0], remaining_uids)
        self.assertIn(uids[1], remaining_uids)
        self.assertIn(uids[2], remaining_uids)

    def test_index_removes_last_file_removes_session(self):
        """Test removing the last file from a session also removes the session."""
        annot = get_session_annotation()
        uids = [self.annexes[0].UID()]
        add_files_to_session(self.signers, uids)
        self.assertEqual(len(annot["sessions"]), 1)

        view = getMultiAdapter((self.annexes[0], self.request), name="remove-item-from-esign-session")
        view.index()
        self.assertEqual(len(annot["sessions"]), 0)
        self.assertEqual(len(annot["uids"]), 0)

    def test_finished_shows_message_and_redirects(self):
        """Test _finished sets a status message and redirects."""
        view = getMultiAdapter((self.annexes[0], self.request), name="remove-item-from-esign-session")
        view._finished()
        messages = IStatusMessage(self.request).show()
        self.assertEqual(len(messages), 1)
        self.assertIn("removed from session", messages[0].message)
        self.assertEqual(self.request.RESPONSE.getHeader("location"), self.annexes[0].absolute_url())


class TestRemoveFromSessionView(BaseRemoveFromSession):
    """Test RemoveFromSessionView browser view."""

    def test_available(self):
        """Test available method returns True."""
        annot = get_session_annotation()
        self.assertFalse(annot["sessions"])
        # only available on "context_uid"
        annex = self.annexes[0]
        view = getMultiAdapter((annex, self.request), name="remove-from-esign-session")
        self.assertFalse(view.available())
        add_files_to_session(self.signers, [annex.UID()])
        self.assertTrue(annot["sessions"])
        self.assertFalse(view.available())
        # available on parent
        folder = annex.aq_parent
        view = getMultiAdapter((folder, self.request), name="remove-from-esign-session")
        self.assertTrue(view.available())
        # call the view so context is removed so no more session
        view()
        self.assertFalse(annot["sessions"])
        self.assertFalse(view.available())
