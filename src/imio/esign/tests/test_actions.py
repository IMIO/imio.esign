# -*- coding: utf-8 -*-
"""actions tests for this package."""
from AccessControl import Unauthorized
from imio.esign.browser.actions import AddToCustomEsignSessionView
from imio.esign.browser.actions import RemoveFromSessionView
from imio.esign.browser.actions import RemoveItemFromSessionView
from imio.esign.browser.actions import SessionAnnotationInfoView
from imio.esign.tests.base import BaseEsignTest
from imio.esign.tests.base import clear_status_messages
from imio.esign.utils import add_files_to_session
from imio.esign.utils import create_session
from imio.esign.utils import get_session_annotation
from plone import api
from plone.app.testing import login
from plone.app.testing import setRoles
from plone.app.testing import TEST_USER_ID
from Products.statusmessages.interfaces import IStatusMessage


try:
    from html import unescape
except ImportError:  # Python 2
    from HTMLParser import HTMLParser

    unescape = HTMLParser().unescape

try:
    string_types = (basestring,)
except NameError:
    string_types = (str,)


class TestRemoveItemFromSessionView(BaseEsignTest):
    """Tests for RemoveItemFromSessionView browser view."""

    def setUp(self):
        super(TestRemoveItemFromSessionView, self).setUp()
        api.user.create(email="user1@sign.com", username="user1", password="password1")  # noqa: S106
        self.folder = self.portal["folder0"]
        self.annexes = [self.portal["folder0"]["annex{}".format(i)] for i in (0, 2, 4)]
        self.signers = [("user1", "user1@sign.com", "User 1", "Position 1")]
        self.view = RemoveItemFromSessionView(self.annexes[0], self.request)

    def test_available(self):
        """Returns False when annex not in session; True once added."""
        self.assertFalse(self.view.available())
        add_files_to_session(self.signers, [a.UID() for a in self.annexes])
        self.assertTrue(self.view.available())

    def test_index(self):
        """Removes file from session; removes entire session when last file is removed."""
        annot = get_session_annotation()
        uids = [a.UID() for a in self.annexes]

        # --- remove one file from a multi-file session ---
        add_files_to_session(self.signers, uids)
        self.assertEqual(len(annot["sessions"]), 1)
        self.assertEqual(len(annot["uids"]), 3)
        session = annot["sessions"][0]
        self.assertEqual(len(session["files"]), 3)
        self.view.index()
        self.assertNotIn(uids[0], annot["uids"])
        self.assertEqual(len(annot["uids"]), 2)
        self.assertEqual(len(session["files"]), 2)
        remaining_uids = [f["uid"] for f in session["files"]]
        self.assertNotIn(uids[0], remaining_uids)
        self.assertIn(uids[1], remaining_uids)
        self.assertIn(uids[2], remaining_uids)

        # --- removing the last file removes the session entirely ---
        add_files_to_session(self.signers, [uids[0]], discriminators=("single",))
        session_count = len(annot["sessions"])
        self.view.index()
        self.assertEqual(len(annot["sessions"]), session_count - 1)
        self.assertNotIn(uids[0], annot["uids"])

    def test_finished(self):
        """Redirects to referrer."""
        self.request.environ["HTTP_REFERER"] = self.annexes[0].absolute_url()
        self.view._finished()
        self.assertEqual(self.request.RESPONSE.getHeader("location"), self.annexes[0].absolute_url())


class TestRemoveFromSessionView(BaseEsignTest):
    """Tests for RemoveFromSessionView browser view."""

    def setUp(self):
        super(TestRemoveFromSessionView, self).setUp()
        api.user.create(email="user1@sign.com", username="user1", password="password1")  # noqa: S106
        self.folder = self.portal["folder0"]
        self.annexes = [self.portal["folder0"]["annex{}".format(i)] for i in (0, 2, 4)]
        self.signers = [("user1", "user1@sign.com", "User 1", "Position 1")]

    def test_available(self):
        """False on the annex itself; True on parent folder once session exists; False again after removal."""
        annot = get_session_annotation()
        self.assertFalse(annot["sessions"])
        annex = self.annexes[0]
        # View on the annex itself is never available (must be on parent/context)
        view = RemoveFromSessionView(self.annexes[0], self.request)
        self.assertFalse(view.available())
        add_files_to_session(self.signers, [annex.UID()])
        self.assertTrue(annot["sessions"])
        self.assertFalse(view.available())
        # Available on parent container once a session exists
        folder_view = RemoveFromSessionView(annex.aq_parent, self.request)
        self.assertTrue(folder_view.available())
        # Calling the view clears the session
        folder_view.index()
        self.assertFalse(annot["sessions"])
        self.assertFalse(folder_view.available())


class TestSessionAnnotationInfoView(BaseEsignTest):
    """Tests for SessionAnnotationInfoView."""

    def setUp(self):
        super(TestSessionAnnotationInfoView, self).setUp()
        api.user.create(email="user1@sign.com", username="user1", password="password1")  # noqa: S106
        api.user.create(email="user2@sign.com", username="user2", password="password2")  # noqa: S106
        self.folder = self.portal["folder0"]
        self.annexes = [self.portal["folder0"]["annex{}".format(i)] for i in (0, 2)]
        self.signers = [
            ("user1", "user1@sign.com", u"User 1", u"Position 1"),
            ("user2", "user2@sign.com", u"User 2", u"Position 2"),
        ]
        self.view = SessionAnnotationInfoView(self.folder, self.request)

    def test_call(self):
        """Raises Unauthorized for non-Manager; returns HTML string for admin."""
        setRoles(self.portal, TEST_USER_ID, ["Member"])
        with self.assertRaises(Unauthorized):
            self.view()
        login(self.layer["app"], "admin")
        self.assertIsInstance(self.view(), string_types)

    def test_render_value(self):
        """Renders dicts, lists, tuples, and strings to escaped HTML."""
        # Dict: empty and with content
        self.assertEqual(self.view._render_value({}), u"{}")
        self.assertEqual(
            self.view._render_value({"key": "val"}),
            u"{\n  &#x27;key&#x27;: &#x27;val&#x27;,\n}",
        )
        # Nested value increases indent level
        self.assertEqual(
            self.view._render_value({"key": ["a"]}),
            u"{\n  &#x27;key&#x27;: [\n    &#x27;a&#x27;,\n  ],\n}",
        )
        # List: empty and with items
        self.assertEqual(self.view._render_value([]), u"[]")
        self.assertEqual(
            self.view._render_value(["a", "b"]),
            u"[\n  &#x27;a&#x27;,\n  &#x27;b&#x27;,\n]",
        )
        # Tuple treated like list
        self.assertEqual(self.view._render_value(()), u"[]")
        # String rendered with u'' prefix
        self.assertEqual(self.view._render_value(u"hello"), u"u&#x27;hello&#x27;")

    def test_uid_to_link(self):
        """Returns clickable link for known UID; span with 'not found' title for unknown."""
        uid = self.folder.UID()
        self.assertEqual(
            self.view._uid_to_link(uid),
            u"<a href='http://nohost/plone/folder0/view' title='/plone/folder0'>Folder 0</a>",
        )
        self.assertEqual(
            self.view._uid_to_link(u"a" * 32),
            u"<span title='not found'>aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa</span>",
        )

    def test_esign_sessions(self):
        """Returns all sessions; supports session_id and context_uid filters; renders HTML correctly."""
        uids = [a.UID() for a in self.annexes]
        add_files_to_session(self.signers, uids, title=u"[ia.parapheo] Session {sign_id}")

        # Add a second session with a different folder and annex
        folder2 = self.portal["folder1"]
        annex2 = folder2["annex1"]
        add_files_to_session(
            self.signers, [annex2.UID()], title=u"[ia.parapheo] Session {sign_id}", discriminators=(u"second",)
        )

        view = SessionAnnotationInfoView(self.folder, self.portal.REQUEST)

        # No filter — returns all sessions
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

        # Rendered HTML for first session
        self.assertEqual(
            unescape(view.esign_session_html(esign_session[1])),
            u"""{{
  'acroform': True,
  'client_id': '0123456',
  'discriminators': [],
  'files': [
    {{
      'context_uid': <a href='http://nohost/plone/folder0/view' title='/plone/folder0'>Folder 0</a>,
      'filename': u'annex0.pdf',
      'scan_id': '012345600000000',
      'status': '',
      'title': u'Annex 0',
      'uid': <a href='http://nohost/plone/folder0/annex0/view' title='/plone/folder0/annex0'>Annex 0</a>,
    }},
    {{
      'context_uid': <a href='http://nohost/plone/folder0/view' title='/plone/folder0'>Folder 0</a>,
      'filename': u'annex2.pdf',
      'scan_id': '012345600000002',
      'status': '',
      'title': u'Annex 2',
      'uid': <a href='http://nohost/plone/folder0/annex2/view' title='/plone/folder0/annex2'>Annex 2</a>,
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
                repr(esign_session[1]["last_update"]),
            ),
        )


class TestAddToCustomEsignSessionView(BaseEsignTest):
    """Tests for AddToCustomEsignSessionView browser view."""

    def setUp(self):
        super(TestAddToCustomEsignSessionView, self).setUp()
        api.user.create(email="user1@sign.com", username="user1", password="password1")  # noqa: S106
        self.annexes = [self.portal["folder0"]["annex{}".format(i)] for i in (0, 2, 4)]
        self.signers = [("user1", "user1@sign.com", "User 1", "Position 1")]
        self.view = AddToCustomEsignSessionView(self.annexes[0], self.request)

    def test_available(self):
        """True when annex not in any session; False once added."""
        self.assertTrue(self.view.available())
        add_files_to_session(self.signers, [self.annexes[0].UID()])
        self.assertFalse(self.view.available())

    def test_call(self):
        """POST dispatches to handle_submit."""
        self.request.form.clear()
        sid, _session = create_session(self.signers, title="")
        self.request.method = "POST"
        self.request.form["form.buttons.submit"] = "Add to session"
        self.request.form["session_id"] = str(sid)
        view = AddToCustomEsignSessionView(self.annexes[0], self.request)
        view()
        annot = get_session_annotation()
        self.assertEqual(annot["uids"][self.annexes[0].UID()], sid)

    def test_has_sessions(self):
        """False with no draft sessions; True once a draft session exists."""
        self.view()
        self.assertFalse(self.view.has_sessions())
        create_session(self.signers, title="")
        view = AddToCustomEsignSessionView(self.annexes[0], self.request)
        view()
        self.assertTrue(view.has_sessions())

    def test_handle_submit(self):
        """All handle_submit branches: missing/invalid/not-found/not-draft id; success; move; same session."""
        annot = get_session_annotation()

        # --- no session_id → warning ---
        create_session(self.signers, title="")
        self.request.method = "POST"
        self.request.form["form.buttons.submit"] = "Add to session"
        result = self.view()
        self.assertIn("No session selected!", result)
        self.assertNotIn(self.annexes[0].UID(), annot["uids"])

        # --- invalid session_id → error ---
        self.request.form["session_id"] = "abc"
        view = AddToCustomEsignSessionView(self.annexes[0], self.request)
        result = view()
        self.assertIn("Invalid session!", result)

        # --- nonexistent session_id → error ---
        self.request.form["session_id"] = "999"
        view = AddToCustomEsignSessionView(self.annexes[0], self.request)
        result = view()
        self.assertIn("Session not found or no longer draft!", result)

        # --- session not draft → error ---
        sid_sent, session_sent = create_session(self.signers, title="")
        session_sent["state"] = "sent"
        self.request.form["session_id"] = str(sid_sent)
        view = AddToCustomEsignSessionView(self.annexes[0], self.request)
        result = view()
        self.assertIn("Session not found or no longer draft!", result)

        # --- success: file added, info message, redirect ---
        sid_draft = [s for s in annot["sessions"] if annot["sessions"][s].get("state") == "draft"][0]
        self.request.form.clear()
        self.request.method = "POST"
        self.request.form["form.buttons.submit"] = "Add to session"
        self.request.form["session_id"] = str(sid_draft)
        view = AddToCustomEsignSessionView(self.annexes[0], self.request)
        view()
        self.assertEqual(annot["uids"][self.annexes[0].UID()], sid_draft)
        file_uids = [f["uid"] for f in annot["sessions"][sid_draft]["files"]]
        self.assertIn(self.annexes[0].UID(), file_uids)
        messages = IStatusMessage(self.request).show()
        self.assertIn("File added to session!", messages[0].message)
        self.assertEqual(messages[0].type, u"info")
        self.assertEqual(
            self.request.RESPONSE.getHeader("location"),
            self.annexes[0].absolute_url(),
        )
        clear_status_messages(self.request)

        # --- move file from one session to another ---
        sid_other, _session_other = create_session(self.signers, title="")
        self.request.form.clear()
        self.request.method = "POST"
        self.request.form["form.buttons.submit"] = "Add to session"
        self.request.form["session_id"] = str(sid_other)
        view = AddToCustomEsignSessionView(self.annexes[0], self.request)
        view()
        self.assertEqual(annot["uids"][self.annexes[0].UID()], sid_other)
        file_uids_other = [f["uid"] for f in annot["sessions"][sid_other]["files"]]
        self.assertIn(self.annexes[0].UID(), file_uids_other)
        clear_status_messages(self.request)

        # --- same session: idempotent re-add ---
        self.request.form.clear()
        self.request.method = "POST"
        self.request.form["form.buttons.submit"] = "Add to session"
        self.request.form["session_id"] = str(sid_other)
        view = AddToCustomEsignSessionView(self.annexes[0], self.request)
        view()
        self.assertEqual(annot["uids"][self.annexes[0].UID()], sid_other)
        self.assertIn(sid_other, annot["sessions"])
