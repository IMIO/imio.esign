# -*- coding: utf-8 -*-
"""actions tests for this package."""
from AccessControl import Unauthorized
from collective.iconifiedcategory.utils import calculate_category_id
from imio.esign.browser.actions import SessionAnnotationInfoView
from imio.esign.testing import IMIO_ESIGN_INTEGRATION_TESTING
from imio.esign.utils import add_files_to_session
from imio.esign.utils import get_session_annotation
from plone import api
from plone.app.testing import login
from plone.app.testing import setRoles
from plone.app.testing import TEST_USER_ID
from plone.namedfile.file import NamedBlobFile
from plone.namedfile.file import NamedBlobImage
from Products.statusmessages.interfaces import IStatusMessage
from zope.component import getMultiAdapter

import collective.iconifiedcategory
import os
import unittest


try:
    from html import unescape
except ImportError:  # Python 2
    from HTMLParser import HTMLParser
    unescape = HTMLParser().unescape

try:
    string_types = (basestring,)
except NameError:
    string_types = (str,)


class BaseRemoveFromSession(unittest.TestCase):
    """Base class to centralize setUp."""

    layer = IMIO_ESIGN_INTEGRATION_TESTING

    def _setup_categories(self):
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

    def setUp(self):
        self.portal = self.layer["portal"]
        self.request = self.portal.REQUEST
        setRoles(self.portal, TEST_USER_ID, ["Manager"])
        self._setup_categories()
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
        annot = get_session_annotation(readonly=False)
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
        annot = get_session_annotation(readonly=False)
        uids = [self.annexes[0].UID()]
        add_files_to_session(self.signers, uids)
        self.assertEqual(len(annot["sessions"]), 1)

        view = getMultiAdapter((self.annexes[0], self.request), name="remove-item-from-esign-session")
        view.index()
        self.assertEqual(len(annot["sessions"]), 0)
        self.assertEqual(len(annot["uids"]), 0)

    def test_finished_shows_message_and_redirects(self):
        """Test _finished sets a status message and redirects."""
        self.request.environ['HTTP_REFERER'] = self.annexes[0].absolute_url()
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
        annot = get_session_annotation(readonly=False)
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


class TestSessionAnnotationInfoView(BaseRemoveFromSession):
    """Test SessionAnnotationInfoView"""

    def setUp(self):
        self.portal = self.layer["portal"]
        self.request = self.portal.REQUEST
        setRoles(self.portal, TEST_USER_ID, ["Manager"])
        self._setup_categories()
        self.folder = api.content.create(
            container=self.portal, type="Folder", id="test_session_folder", title="Test Session Folder"
        )
        tests_dir = os.path.dirname(__file__)
        self.annexes = []
        for i in range(2):
            with open(os.path.join(tests_dir, "annex1.pdf"), "rb") as f:
                annex = api.content.create(
                    container=self.folder,
                    type="annex",
                    id="annex{}".format(i),
                    title=u"Annex {}".format(i),
                    content_category=calculate_category_id(self.portal["annexes_types"]["annexes"]["to_sign"]),
                    scan_id="012345600000{:02d}".format(i),
                    file=NamedBlobFile(data=f.read(), filename=u"annex{}.pdf".format(i), contentType="application/pdf"),
                )
                self.annexes.append(annex)
        self.signers = [
            ("user1", "user1@sign.com", u"User 1", u"Position 1"),
            ("user2", "user2@sign.com", u"User 2", u"Position 2"),
        ]
        self.view = SessionAnnotationInfoView(self.folder, self.portal.REQUEST)

    def test_call(self):
        setRoles(self.portal, TEST_USER_ID, ["Member"])
        with self.assertRaises(Unauthorized):
            self.view()
        login(self.layer["app"], "admin")
        self.assertIsInstance(self.view(), string_types)

    def test_render_value(self):
        # Dict
        self.assertEqual(self.view._render_value({}), u"{}")
        self.assertEqual(
            self.view._render_value({"key": "val"}),
            u"{\n  &#x27;key&#x27;: &#x27;val&#x27;,\n}",
        )

        # Indentation: nested value increases indent level
        self.assertEqual(
            self.view._render_value({"key": ["a"]}),
            u"{\n  &#x27;key&#x27;: [\n    &#x27;a&#x27;,\n  ],\n}",
        )

        # List
        self.assertEqual(self.view._render_value([]), u"[]")
        self.assertEqual(
            self.view._render_value(["a", "b"]),
            u"[\n  &#x27;a&#x27;,\n  &#x27;b&#x27;,\n]",
        )

        # Tuple
        self.assertEqual(self.view._render_value(()), u"[]")

        # String
        self.assertEqual(self.view._render_value(u"hello"), u"u&#x27;hello&#x27;")

    def test_uid_to_link(self):
        uid = self.folder.UID()
        result = self.view._uid_to_link(uid)
        self.assertEqual(
            result,
            u"<a href='http://nohost/plone/test_session_folder/view' title='/plone/test_session_folder'>Test Session Folder</a>",
        )

        result = self.view._uid_to_link(u"a" * 32)
        self.assertEqual(
            result,
            u"<span title='not found'>aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa</span>",
        )

    def test_esign_sessions(self):
        uids = [a.UID() for a in self.annexes]
        add_files_to_session(self.signers, uids, title=u"[ia.parapheo] Session {sign_id}")

        # Add a second session with a separate folder/annex
        folder2 = api.content.create(
            container=self.portal, type="Folder", id="test_session_folder2", title="Test Session Folder 2"
        )
        tests_dir = os.path.dirname(__file__)
        with open(os.path.join(tests_dir, "annex1.pdf"), "rb") as f:
            annex2 = api.content.create(
                container=folder2,
                type="annex",
                id="annex2",
                title=u"Annex 2",
                content_category=calculate_category_id(self.portal["annexes_types"]["annexes"]["to_sign"]),
                scan_id="01234560000002",
                file=NamedBlobFile(data=f.read(), filename=u"annex2.pdf", contentType="application/pdf"),
            )
        add_files_to_session(self.signers, [annex2.UID()], title=u"[ia.parapheo] Session {sign_id}",
                             discriminators=(u"second",))

        view = SessionAnnotationInfoView(self.folder, self.portal.REQUEST)

        # No filter params — returns all sessions
        esign_sessions = view.esign_sessions
        self.assertEqual(len(esign_sessions), 2)
        esign_session = esign_sessions[0]
        self.assertIsInstance(esign_session, tuple)
        self.assertEqual(esign_session[0], 0)

        # Filter by session_id
        self.portal.REQUEST.form["session_id"] = "0"
        self.assertEqual(len(view.esign_sessions), 1)
        self.assertEqual(view.esign_sessions[0][0], 0)
        self.portal.REQUEST.form["session_id"] = "1"
        self.assertEqual(len(view.esign_sessions), 1)
        self.assertEqual(view.esign_sessions[0][0], 1)
        self.portal.REQUEST.form["session_id"] = "999"
        self.assertEqual(len(view.esign_sessions), 0)
        del self.portal.REQUEST.form["session_id"]

        # Filter by context_uid
        self.portal.REQUEST.form["context_uid"] = self.folder.UID()
        self.assertEqual(len(view.esign_sessions), 1)
        self.assertEqual(view.esign_sessions[0][0], 0)
        self.portal.REQUEST.form["context_uid"] = folder2.UID()
        self.assertEqual(len(view.esign_sessions), 1)
        self.assertEqual(view.esign_sessions[0][0], 1)
        self.portal.REQUEST.form["context_uid"] = u"a" * 32
        self.assertEqual(len(view.esign_sessions), 0)
        del self.portal.REQUEST.form["context_uid"]

        # Test rendered HTML
        self.assertEqual(
            unescape(view.esign_session_html(esign_session[1])),
            u"""{{
  'acroform': True,
  'client_id': '0123456',
  'discriminators': [],
  'files': [
    {{
      'context_uid': <a href='http://nohost/plone/test_session_folder/view' title='/plone/test_session_folder'>Test Session Folder</a>,
      'filename': u'annex0.pdf',
      'scan_id': '01234560000000',
      'status': '',
      'title': u'Annex 0',
      'uid': <a href='http://nohost/plone/test_session_folder/annex0/view' title='/plone/test_session_folder/annex0'>Annex 0</a>,
    }},
    {{
      'context_uid': <a href='http://nohost/plone/test_session_folder/view' title='/plone/test_session_folder'>Test Session Folder</a>,
      'filename': u'annex1.pdf',
      'scan_id': '01234560000001',
      'status': '',
      'title': u'Annex 1',
      'uid': <a href='http://nohost/plone/test_session_folder/annex1/view' title='/plone/test_session_folder/annex1'>Annex 1</a>,
    }},
  ],
  'last_update': {},
  'returns': [],
  'seal': None,
  'sign_id': '012345600000',
  'sign_url': None,
  'signers': [
    {{
      'email': 'user1@sign.com',
      'fullname': u'User 1',
      'position': u'Position 1',
      'status': '',
      'userid': 'user1',
    }},
    {{
      'email': 'user2@sign.com',
      'fullname': u'User 2',
      'position': u'Position 2',
      'status': '',
      'userid': 'user2',
    }},
  ],
  'size': 13936,
  'state': 'draft',
  'title': u'[ia.parapheo] Session 012345600000',
  'watchers': [],
}}""".format(
                repr(esign_session[1]['last_update']),
            ),
        )
