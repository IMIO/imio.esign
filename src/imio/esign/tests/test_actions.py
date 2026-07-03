# -*- coding: utf-8 -*-
"""actions tests for this package."""
from AccessControl import Unauthorized
from datetime import datetime
from imio.esign.browser.actions import RecreateSessionFormView
from imio.esign.browser.actions import RecreateSessionView
from imio.esign.browser.actions import RemoveFromSessionView
from imio.esign.browser.actions import RemoveItemFromSessionView
from imio.esign.browser.actions import SessionAnnotationInfoView
from imio.esign.tests.base import BaseEsignTest
from imio.esign.utils import add_files_to_session
from imio.esign.utils import get_session_annotation
from plone import api
from plone.app.testing import login
from plone.app.testing import logout
from plone.app.testing import setRoles
from plone.app.testing import TEST_USER_ID
from plone.app.testing import TEST_USER_NAME

import json


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
            u"<a href='http://nohost/plone/folder0/view' title='/plone/folder0'>Folder 0</a> ({0})".format(uid)
        )
        self.assertEqual(
            self.view._uid_to_link(u"a" * 32),
            u"<span title='not found'>aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa</span>"
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
        folder_uid = self.folder.UID()
        self.assertEqual(
            unescape(view.esign_session_html(esign_session[1])),
            u"""{{
  'acroform': True,
  'client_id': '0123456',
  'discriminators': [],
  'files': [
    {{
      'context_uid': <a href='http://nohost/plone/folder0/view' title='/plone/folder0'>Folder 0</a> ({0}),
      'filename': u'annex0.pdf',
      'scan_id': '012345600000000',
      'status': '',
      'title': u'Annex 0',
      'uid': <a href='http://nohost/plone/folder0/annex0/view' title='/plone/folder0/annex0'>Annex 0</a> ({1}),
    }},
    {{
      'context_uid': <a href='http://nohost/plone/folder0/view' title='/plone/folder0'>Folder 0</a> ({2}),
      'filename': u'annex2.pdf',
      'scan_id': '012345600000002',
      'status': '',
      'title': u'Annex 2',
      'uid': <a href='http://nohost/plone/folder0/annex2/view' title='/plone/folder0/annex2'>Annex 2</a> ({3}),
    }},
  ],
  'last_update': {4},
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
    folder_uid,
    self.annexes[0].UID(),
    folder_uid,
    self.annexes[1].UID(),
    repr(esign_session[1]["last_update"]),
            ),
        )


class TestRecreateSessionView(BaseEsignTest):
    """Tests for RecreateSessionView browser view."""

    def setUp(self):
        super(TestRecreateSessionView, self).setUp()
        api.user.create(email="user1@sign.com", username="user1", password="password1")
        api.user.create(email="user2@sign.com", username="user2", password="password2")
        self.folder = self.portal["folder0"]
        self.annexes = [self.portal["folder0"]["annex{}".format(i)] for i in (0, 2, 4)]
        self.signers = [
            ("user1", "user1@sign.com", u"User 1", u"Position 1"),
            ("user2", "user2@sign.com", u"User 2", u"Position 2"),
        ]

    def _make_non_draft_session(self, state="to_sign", **kwargs):
        """Create a session via add_files_to_session and flip its state to ``state``."""
        session_id, session = add_files_to_session(
            self.signers,
            [a.UID() for a in self.annexes],
            title=u"Original title",
            watchers=[u"watcher@sign.com"],
            discriminators=(u"disc1",),
            **kwargs
        )[-1]
        session["state"] = state
        return session_id, session

    def test_may_recreate_session(self):
        """True for Manager; False for Member."""
        view = RecreateSessionView(self.portal, self.request)
        self.assertTrue(view.may_recreate_session())
        setRoles(self.portal, TEST_USER_ID, ["Member"])
        self.assertFalse(view.may_recreate_session())

    def test_call(self):
        """Guards (unauthorized), missing/unknown/draft session, recreation,
        no-merge with a matching draft, old-session deletion, and partial
        selection via ``file_uids`` (subset moved to new session, unselected
        files stay in the old session, empty/invalid selections recreate nothing)."""
        annot = get_session_annotation()

        # --- Unauthorized: non-Manager ---
        setRoles(self.portal, TEST_USER_ID, ["Member"])
        with self.assertRaises(Unauthorized):
            RecreateSessionView(self.portal, self.request)()
        setRoles(self.portal, TEST_USER_ID, ["Manager"])

        # --- Unauthorized: anonymous ---
        logout()
        with self.assertRaises(Unauthorized):
            RecreateSessionView(self.portal, self.request)()
        login(self.portal, TEST_USER_NAME)

        # --- No session_id: redirect, no new session created ---
        old_id, old = self._make_non_draft_session()
        old_files_uids = [f["uid"] for f in old["files"]]
        view = RecreateSessionView(self.portal, self.request)
        result = view()
        self.assertEqual(result, self.portal.absolute_url() + "/@@parapheo")
        self.assertIsNone(view._new_session_id)
        self.assertEqual(list(annot["sessions"].keys()), [old_id])

        # --- Invalid session_id: no new session ---
        self.request.form["esign_session_id"] = "wrong"
        view = RecreateSessionView(self.portal, self.request)
        view()
        self.assertIsNone(view._new_session_id)
        self.assertEqual(len(annot["sessions"]), 1)
        del self.request.form["esign_session_id"]

        # --- Unknown session_id: no new session ---
        self.request.form["esign_session_id"] = "9999"
        view = RecreateSessionView(self.portal, self.request)
        view()
        self.assertIsNone(view._new_session_id)
        self.assertEqual(len(annot["sessions"]), 1)
        del self.request.form["esign_session_id"]

        # --- Draft session blocked ---
        annot["sessions"][old_id]["state"] = "draft"
        self.request.form["esign_session_id"] = str(old_id)
        view = RecreateSessionView(self.portal, self.request)
        view()
        self.assertIsNone(view._new_session_id)
        self.assertEqual(len(annot["sessions"]), 1)
        annot["sessions"][old_id]["state"] = "to_sign"
        del self.request.form["esign_session_id"]

        # --- Successful recreation: new draft with same files, signers, metadata ---
        self.request.form["esign_session_id"] = str(old_id)
        view = RecreateSessionView(self.portal, self.request)
        view()
        new_id = view._new_session_id
        self.assertIsNotNone(new_id)
        self.assertNotEqual(new_id, old_id)
        new_session = annot["sessions"][new_id]
        self.assertEqual(new_session["state"], "draft")
        self.assertEqual([f["uid"] for f in new_session["files"]], old_files_uids)
        for nu, ou in zip(new_session["signers"], old["signers"]):
            self.assertEqual(
                (nu["userid"], nu["email"], nu["fullname"], nu["position"]),
                (ou["userid"], ou["email"], ou["fullname"], ou["position"]),
            )
        self.assertEqual(set(new_session["discriminators"]), {u"disc1"})
        self.assertEqual(list(new_session["watchers"]), [u"watcher@sign.com"])
        self.assertEqual(new_session["title"], u"Session 1")
        self.assertEqual(new_session.get("recreated_from"), old_id)
        # Old session deleted
        self.assertNotIn(old_id, annot["sessions"])
        for uid in old_files_uids:
            self.assertEqual(annot["uids"][uid], new_id)
        del self.request.form["esign_session_id"]

        # --- No merge: recreation always creates a brand-new session even when a
        #     matching draft (same signers + discriminators) already exists ---
        second_old_id, _ = self._make_non_draft_session()
        matching_draft_id, _ = add_files_to_session(
            self.signers,
            [self.portal["folder1"]["annex1"].UID()],
            discriminators=(u"disc1",),
        )[-1]
        sessions_before = set(annot["sessions"].keys())
        self.request.form["esign_session_id"] = str(second_old_id)
        view = RecreateSessionView(self.portal, self.request)
        view()
        brand_new_id = view._new_session_id
        self.assertIsNotNone(brand_new_id)
        self.assertNotIn(brand_new_id, sessions_before)
        self.assertNotEqual(brand_new_id, matching_draft_id)
        self.assertNotIn(second_old_id, annot["sessions"])
        del self.request.form["esign_session_id"]

        # --- Partial selection: keep only the first two files ---
        partial_old_id, partial_old = self._make_non_draft_session()
        partial_files_uids = [f["uid"] for f in partial_old["files"]]
        kept, dropped = partial_files_uids[:2], partial_files_uids[2:]
        self.request.form["esign_session_id"] = str(partial_old_id)
        self.request.form["file_uids"] = json.dumps(kept)
        view = RecreateSessionView(self.portal, self.request)
        view()
        partial_new_id = view._new_session_id
        self.assertIsNotNone(partial_new_id)
        partial_new_session = annot["sessions"][partial_new_id]
        self.assertEqual([f["uid"] for f in partial_new_session["files"]], kept)
        # kept files now belong to the new session; unselected files stay in the old session
        for uid in kept:
            self.assertEqual(annot["uids"][uid], partial_new_id)
        for uid in dropped:
            self.assertEqual(annot["uids"][uid], partial_old_id)
        self.assertIn(partial_old_id, annot["sessions"])
        self.assertEqual([f["uid"] for f in annot["sessions"][partial_old_id]["files"]], dropped)
        del self.request.form["file_uids"]
        del self.request.form["esign_session_id"]

        # --- Empty selection: nothing recreated ---
        other_id, _ = self._make_non_draft_session()
        count_before = len(annot["sessions"])
        self.request.form["esign_session_id"] = str(other_id)
        self.request.form["file_uids"] = "[]"
        view = RecreateSessionView(self.portal, self.request)
        view()
        self.assertIsNone(view._new_session_id)
        self.assertEqual(len(annot["sessions"]), count_before)
        self.assertIn(other_id, annot["sessions"])

        # --- Invalid JSON: treated as empty selection, nothing recreated ---
        self.request.form["file_uids"] = "not-json"
        view = RecreateSessionView(self.portal, self.request)
        view()
        self.assertIsNone(view._new_session_id)
        self.assertEqual(len(annot["sessions"]), count_before)
        del self.request.form["file_uids"]
        del self.request.form["esign_session_id"]

    def test_get_new_session_title_default(self):
        """The base view returns an empty title, so create_session mints its own."""
        old_id, old = self._make_non_draft_session()
        view = RecreateSessionView(self.portal, self.request)
        self.assertEqual(view.get_new_session_title(old, old_id), u"")

    def test_get_new_session_title_override(self):
        """A consuming app can set the recreated session title via the hook."""
        annot = get_session_annotation()
        old_id, old = self._make_non_draft_session()

        class CustomRecreateSessionView(RecreateSessionView):
            def get_new_session_title(self, old, old_session_id):
                return old.get("title", u"")

        self.request.form["esign_session_id"] = str(old_id)
        view = CustomRecreateSessionView(self.portal, self.request)
        view()
        new_id = view._new_session_id
        self.assertIsNotNone(new_id)
        self.assertEqual(annot["sessions"][new_id]["title"], u"Original title")
        del self.request.form["esign_session_id"]


class TestRecreateSessionFormView(BaseEsignTest):
    """Tests for the RecreateSessionFormView overlay form."""

    def setUp(self):
        super(TestRecreateSessionFormView, self).setUp()
        api.user.create(email="user1@sign.com", username="user1", password="password1")
        api.user.create(email="user2@sign.com", username="user2", password="password2")
        self.annexes = [self.portal["folder0"]["annex{}".format(i)] for i in (0, 2, 4)]
        self.signers = [
            ("user1", "user1@sign.com", u"User 1", u"Position 1"),
            ("user2", "user2@sign.com", u"User 2", u"Position 2"),
        ]

    def _make_session(self, state="to_sign", returns=None):
        session_id, session = add_files_to_session(
            self.signers,
            [a.UID() for a in self.annexes],
            title=u"Original title",
        )[-1]
        session["state"] = state
        if returns is not None:
            session["returns"].extend(returns)
        return session_id, session

    def test_may_recreate_session(self):
        """True for Manager; False for Member."""
        view = RecreateSessionFormView(self.portal, self.request)
        self.assertTrue(view.may_recreate_session())
        setRoles(self.portal, TEST_USER_ID, ["Member"])
        self.assertFalse(view.may_recreate_session())

    def test_unauthorized(self):
        """Member and anonymous users cannot open the form."""
        session_id, _ = self._make_session()
        self.request.form["esign_session_id"] = str(session_id)
        setRoles(self.portal, TEST_USER_ID, ["Member"])
        with self.assertRaises(Unauthorized):
            RecreateSessionFormView(self.portal, self.request)()
        setRoles(self.portal, TEST_USER_ID, ["Manager"])
        logout()
        with self.assertRaises(Unauthorized):
            RecreateSessionFormView(self.portal, self.request)()
        login(self.portal, TEST_USER_NAME)

    def test_invalid_and_draft_sessions_render_error(self):
        """Missing/unknown/draft sessions render an error snippet, not the form."""
        # Missing id
        view = RecreateSessionFormView(self.portal, self.request)
        self.assertIn("portalMessage error", view())
        # Unknown id
        self.request.form["esign_session_id"] = "9999"
        view = RecreateSessionFormView(self.portal, self.request)
        self.assertIn("portalMessage error", view())
        # Draft id
        draft_id, _ = self._make_session(state="draft")
        self.request.form["esign_session_id"] = str(draft_id)
        view = RecreateSessionFormView(self.portal, self.request)
        self.assertIn("portalMessage error", view())
        del self.request.form["esign_session_id"]

    def test_files_and_render(self):
        """The form lists every file of the session."""
        session_id, session = self._make_session()
        self.request.form["esign_session_id"] = str(session_id)
        view = RecreateSessionFormView(self.portal, self.request)
        html = view()
        self.assertEqual(len(view.files()), len(self.annexes))
        for f in session["files"]:
            self.assertIn(f["uid"], html)
        self.assertIn("recreate-file-cb", html)
        del self.request.form["esign_session_id"]

    def test_refused_reason(self):
        """The refusal reason is read from the code 52 ``returns`` entry."""
        reason = u"J'ai détecté un problème dans le document"
        returns = [
            (21, u"to_sign", {u"sign_session_url": u"http://x"}, u"created", datetime(2026, 6, 1, 14, 40)),
            (52, u"refused", {u"reason": reason, u"user": u"user1@sign.com"},
             u"Document has been declined", datetime(2026, 6, 1, 14, 55)),
        ]
        refused_id, _ = self._make_session(state="refused", returns=returns)
        self.request.form["esign_session_id"] = str(refused_id)
        view = RecreateSessionFormView(self.portal, self.request)
        html = view()
        self.assertEqual(view.refused_reason(), reason)
        self.assertIn("Refusal reason", html)
        del self.request.form["esign_session_id"]

    def test_no_refused_reason_when_not_refused(self):
        """No reason for non-refused sessions, or refused without a code 52 entry."""
        # Non-refused session
        session_id, _ = self._make_session(state="to_sign")
        self.request.form["esign_session_id"] = str(session_id)
        view = RecreateSessionFormView(self.portal, self.request)
        view()
        self.assertEqual(view.refused_reason(), u"")
        del self.request.form["esign_session_id"]
        # Refused session but no code 52 entry
        refused_id, _ = self._make_session(state="refused", returns=[])
        self.request.form["esign_session_id"] = str(refused_id)
        view = RecreateSessionFormView(self.portal, self.request)
        view()
        self.assertEqual(view.refused_reason(), u"")
        del self.request.form["esign_session_id"]
