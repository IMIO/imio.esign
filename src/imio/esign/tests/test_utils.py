# -*- coding: utf-8 -*-
"""utils tests for this package."""
from collections import OrderedDict
from datetime import date
from datetime import timedelta
from imio.esign.config import get_esign_registry_max_session_files
from imio.esign.config import get_esign_registry_max_session_size
from imio.esign.config import set_esign_registry_external_watchers
from imio.esign.config import set_esign_registry_max_session_files
from imio.esign.config import set_esign_registry_max_session_size
from imio.esign.tests.base import BaseEsignTest
from imio.esign.utils import add_files_to_session
from imio.esign.utils import create_external_session
from imio.esign.utils import create_session
from imio.esign.utils import get_file_download_url
from imio.esign.utils import get_file_info
from imio.esign.utils import get_filesize
from imio.esign.utils import get_max_download_date
from imio.esign.utils import get_session_annotation
from imio.esign.utils import get_session_info
from imio.esign.utils import get_sessions_for
from imio.esign.utils import get_suid_from_uuid
from imio.esign.utils import remove_context_from_session
from imio.esign.utils import remove_files_from_session
from imio.esign.utils import remove_session
from imio.helpers.content import uuidToObject
from imio.pyutils.utils import shortuid_decode_id
from mock import Mock
from mock import patch
from plone import api
from plone.namedfile.file import NamedBlobFile
from zope.annotation import IAnnotations
from zope.event import notify
from zope.lifecycleevent import ObjectModifiedEvent

import json
import os


class TestUtils(BaseEsignTest):
    def setUp(self):
        super(TestUtils, self).setUp()
        api.user.create(email="user1@sign.com", username="user1", password="password1")  # noqa: S106
        api.user.create(email="user2@sign.com", username="user2", password="password2")  # noqa: S106
        self.folders = [self.portal["folder0"], self.portal["folder1"]]
        self.uids = [self.portal["folder{}".format(i % 2)]["annex{}".format(i)].UID() for i in range(12)]

    def test_add_files_to_session(self):
        """add_files_to_session: session creation, discrimination, reuse, size splitting,
        count splitting, completed sessions not reused, duplicate filenames, and idempotent
        metadata update."""
        root_annot = IAnnotations(self.portal)
        self.assertNotIn("imio.esign", root_annot)
        signers = [
            ("user1", "user1@sign.com", "User 1", "Position 1"),
            ("user2", "user2@sign.com", "User 2", "Position 2"),
        ]

        # --- create first session ---
        sid, session = add_files_to_session(signers, (self.uids[0],), title="my title",
                                            watchers=("stalker@sign.com",))[-1]
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
        self.assertEqual(session["size"], 6968)

        # --- same signers → session reused; duplicate filename renamed ---
        signers[1] = ("user2", "user2@sign.com", "User 2", "Position 2b")  # position change is non-discriminant
        annex1_obj = uuidToObject(uuid=self.uids[1], unrestricted=True)
        annex1_obj.file.filename = u"annex0.pdf"
        sid, session = add_files_to_session(signers, (self.uids[1],))[-1]
        self.assertEqual(sid, 0)
        self.assertEqual(annot["numbering"], 1)
        self.assertEqual(len(annot["sessions"]), 1)
        self.assertEqual(len(annot["uids"]), 2)
        self.assertIn(self.uids[1], annot["uids"])
        self.assertEqual(len(annot["c_uids"]), 2)
        self.assertIn(self.folders[1].UID(), annot["c_uids"])
        self.assertEqual(len(session["files"]), 2)
        self.assertEqual(session["files"][1]["filename"], u"annex0-1.pdf")
        self.assertEqual(len(annot["c_uids"][self.folders[1].UID()]), 1)
        self.assertEqual(session["size"], 6968 + 7014)  # annex1 + annex2

        # --- new discriminator → new session ---
        sid, session = add_files_to_session(signers, (self.uids[2],), discriminators=("council1",))[-1]
        self.assertEqual(sid, 1)
        self.assertEqual(annot["numbering"], 2)
        self.assertEqual(len(annot["sessions"]), 2)
        self.assertEqual(len(annot["uids"]), 3)
        self.assertIn(self.uids[2], annot["uids"])
        self.assertEqual(len(session["files"]), 1)
        self.assertEqual(len(session["watchers"]), 0)

        # --- same discriminator → reuse session ---
        sid, session = add_files_to_session(signers, (self.uids[3],), discriminators=("council1",))[-1]
        self.assertEqual(sid, 1)
        self.assertEqual(annot["numbering"], 2)
        self.assertEqual(len(annot["sessions"]), 2)
        self.assertEqual(len(annot["uids"]), 4)
        self.assertIn(self.uids[3], annot["uids"])
        self.assertEqual(len(session["files"]), 2)

        # --- different discriminator → new session ---
        sid, _session = add_files_to_session(signers, (self.uids[4],), discriminators=("council2",))[-1]
        self.assertEqual(sid, 2)

        # --- explicit session_id overrides discrimination ---
        sid, _session = add_files_to_session(signers, (self.uids[5],), session_id=0, discriminators=("council3",))[-1]
        self.assertEqual(sid, 0)

        # --- unfound session_id → new session ---
        sid, _session = add_files_to_session(signers, (self.uids[6],), session_id=999, discriminators=("council3",))[-1]
        self.assertEqual(sid, 3)

        # --- different signers → new session ---
        sid, _session = add_files_to_session([signers[0]], (self.uids[7],))[-1]
        self.assertEqual(sid, 4)

        # --- different seal → new session ---
        sid, _session = add_files_to_session(signers, (self.uids[8],), seal="seal1")[-1]
        self.assertEqual(sid, 5)

        # --- different acroform → new session ---
        sid, _session = add_files_to_session(signers, (self.uids[9],), acroform=False)[-1]
        self.assertEqual(sid, 6)
        self.assertEqual(len(annot["uids"]), 10)
        self.assertEqual(len(annot["c_uids"]), 2)
        self.assertEqual(len(annot["c_uids"][self.folders[0].UID()]), 5)
        self.assertEqual(len(annot["c_uids"][self.folders[1].UID()]), 5)
        self.assertEqual(len(annot["sessions"]), 7)

        # --- no signers → new session ---
        sid, session = add_files_to_session([], (self.uids[10],), seal="seal2")[-1]
        self.assertEqual(sid, 7)
        self.assertEqual(len(annot["sessions"]), 8)
        self.assertEqual(session["signers"], [])
        self.assertEqual(session["seal"], "seal2")

        # --- same seal but session already sent → new session ---
        session["state"] = "sent"
        sid, _session = add_files_to_session([], (self.uids[11],), seal="seal2")[-1]
        self.assertEqual(sid, 8)
        self.assertEqual(len(annot["sessions"]), 9)

        # --- duplicate filenames: each gets a numbered suffix ---
        del root_annot["imio.esign"]
        for i in range(3):
            api.content.get(UID=self.uids[i]).file.filename = u"same_filename.pdf"
        s, ses = add_files_to_session(signers, (self.uids[0],))[-1]
        self.assertEqual(len(ses["files"]), 1)
        self.assertEqual(ses["files"][0]["filename"], "same_filename.pdf")
        s, ses = add_files_to_session(signers, (self.uids[1],), session_id=s)[-1]
        self.assertEqual(len(ses["files"]), 2)
        self.assertIn("same_filename-1.pdf", [f["filename"] for f in ses["files"]])
        s, ses = add_files_to_session(signers, (self.uids[2],), session_id=s)[-1]
        self.assertEqual(len(ses["files"]), 3)
        filenames = [f["filename"] for f in ses["files"]]
        self.assertIn("same_filename.pdf", filenames)
        self.assertIn("same_filename-1.pdf", filenames)
        self.assertIn("same_filename-2.pdf", filenames)

        # --- re-adding same file updates metadata, does not duplicate ---
        del root_annot["imio.esign"]
        annex0_uid = self.uids[0]
        annex0 = api.content.get(UID=annex0_uid)
        annex0.file.filename = u"annex0.pdf"
        # reset annex1 filename which was changed in the duplicate-filename block above
        annex1_reset = api.content.get(UID=self.uids[1])
        annex1_reset.file.filename = u"annex1.pdf"
        sid, ses = add_files_to_session(signers, (annex0_uid,))[-1]
        self.assertEqual(sid, 0)
        self.assertEqual(len(ses["files"]), 1)
        self.assertEqual(ses["files"][0]["filename"], "annex0.pdf")
        self.assertEqual(ses["files"][0]["title"], "Annex 0")
        self.assertEqual(ses["size"], 6968)
        annex0.file.filename = u"new_annex0.pdf"
        annex0.setTitle("New Annex 0")
        sid, ses = add_files_to_session(signers, (annex0_uid,))[-1]
        self.assertEqual(sid, 0)
        self.assertEqual(len(ses["files"]), 1)
        self.assertEqual(ses["files"][0]["filename"], "new_annex0.pdf")
        self.assertEqual(ses["files"][0]["title"], "New Annex 0")
        self.assertEqual(ses["size"], 6968)
        sid, ses = add_files_to_session(signers, (annex0_uid,))[-1]
        self.assertEqual(sid, 0)
        self.assertEqual(len(ses["files"]), 1)
        self.assertEqual(ses["files"][0]["filename"], "new_annex0.pdf")
        self.assertEqual(ses["files"][0]["title"], "New Annex 0")
        self.assertEqual(ses["size"], 6968)
        annex1_uid = self.uids[1]
        annex1 = api.content.get(UID=annex1_uid)
        sid, ses = add_files_to_session(signers, (annex1_uid,))[-1]
        self.assertEqual(sid, 0)
        self.assertEqual(len(ses["files"]), 2)
        self.assertEqual(ses["files"][1]["filename"], "annex1.pdf")
        self.assertEqual(ses["files"][1]["title"], "Annex 1")
        self.assertEqual(ses["size"], 13982)
        annex1.setTitle("New Annex 1")
        with open(os.path.join(os.path.dirname(__file__), "annex1.pdf"), "rb") as f:
            annex1.file = NamedBlobFile(data=f.read(), filename=u"new_annex1.pdf", contentType="application/pdf")
        notify(ObjectModifiedEvent(annex1))
        self.assertEqual(len(ses["files"]), 2)
        self.assertEqual(ses["files"][1]["filename"], "new_annex1.pdf")
        self.assertEqual(ses["files"][1]["title"], "New Annex 1")
        self.assertEqual(ses["files"][1]["scan_id"], "012345600000001")
        self.assertEqual(ses["size"], 13936)
        with open(os.path.join(os.path.dirname(__file__), "annex1.pdf"), "rb") as f:
            annex1.file = NamedBlobFile(data=f.read(), filename=u"new_annex0.pdf", contentType="application/pdf")
        annex1.scan_id = "012345600000002"
        notify(ObjectModifiedEvent(annex1))
        self.assertEqual(ses["files"][1]["filename"], "new_annex0-1.pdf")
        self.assertEqual(ses["files"][1]["scan_id"], "012345600000002")
        annex2_uid = self.uids[2]
        annex2 = api.content.get(UID=annex2_uid)
        notify(ObjectModifiedEvent(annex2))
        remove_files_from_session((annex0_uid,))
        self.assertEqual(ses["size"], 6968)
        # works also when annex deleted
        last_annex_uid = self.uids[-1]
        last_annex = api.content.get(UID=last_annex_uid)
        sid, ses = add_files_to_session(signers, (last_annex_uid,))[-1]
        self.assertEqual(ses["size"], 13982)
        api.content.delete(last_annex)
        self.assertFalse(api.portal.get_tool('portal_catalog')(UID=last_annex_uid))
        self.assertEqual(ses["size"], 6968)

        # --- size-based session splitting ---
        del root_annot["imio.esign"]
        annex0.file.filename = u"annex0.pdf"
        sid0, ses0 = add_files_to_session(signers, (annex0_uid,))[-1]
        self.assertEqual(sid0, 0)
        self.assertEqual(ses0["size"], 6968)
        ses0["size"] = 1 * 1024 ** 2 - 1
        prev_max = get_esign_registry_max_session_size()
        self.addCleanup(set_esign_registry_max_session_size, prev_max)
        set_esign_registry_max_session_size(1)
        sid1, ses1 = add_files_to_session(signers, (self.uids[1],))[-1]
        self.assertEqual(sid1, 1)
        self.assertIsNot(ses1, ses0)
        self.assertEqual(ses1["size"], 6968)
        sid2, ses2 = add_files_to_session(signers, (self.uids[2],))[-1]
        self.assertEqual(sid2, 1)
        self.assertIs(ses2, ses1)
        self.assertEqual(ses2["size"], 6968 + 6968)

        # --- count-based session splitting: a single batch dispatched across several sessions ---
        del root_annot["imio.esign"]
        prev_max_files = get_esign_registry_max_session_files()
        self.addCleanup(set_esign_registry_max_session_files, prev_max_files)
        set_esign_registry_max_session_files(2)
        signers = [("user1", "user1@sign.com", "User 1", "P1")]
        sid, session = add_files_to_session(signers, tuple(self.uids[:5]))[-1]
        annot = get_session_annotation()
        sessions = annot["sessions"]
        self.assertEqual(len(sessions), 3)
        self.assertEqual([len(sessions[i]["files"]) for i in (0, 1, 2)], [2, 2, 1])
        self.assertEqual(sessions[0]["state"], "draft_full")
        self.assertEqual(sessions[1]["state"], "draft_full")
        self.assertEqual(sessions[2]["state"], "draft")
        # return value is for the last file added
        self.assertEqual(sid, 2)
        self.assertIs(session, sessions[2])

        # --- a session marked 'draft_full' is never reused, even if the limit is later raised ---
        del root_annot["imio.esign"]
        set_esign_registry_max_session_files(2)
        # First batch: 3 files → session 0 gets 2 (and is closed), session 1 gets 1 (draft)
        add_files_to_session(signers, tuple(self.uids[:3]))
        annot = get_session_annotation()
        self.assertEqual(annot["sessions"][0]["state"], "draft_full")
        self.assertEqual(annot["sessions"][1]["state"], "draft")
        # Raise the max back to a value that would mathematically allow reusing session 0
        set_esign_registry_max_session_files(10)
        sid, session = add_files_to_session(signers, (self.uids[3],))[-1]
        # Session 0 stays draft_full; new file lands in the existing draft (session 1), not in 0
        self.assertEqual(annot["sessions"][0]["state"], "draft_full")
        self.assertEqual(sid, 1)
        self.assertEqual(len(annot["sessions"][1]["files"]), 2)

    def test_add_files_ordering_by_context(self):
        """add_files_to_session: files are ordered by their sibling position within their context."""
        def reset_annotation():
            annot = get_session_annotation()
            annot["sessions"].clear()
            annot["uids"].clear()
            annot["c_uids"].clear()
            annot["numbering"] = 0

        signers = [("user1", "user1@sign.com", "User 1", "Position 1")]

        # Case 1: uid[0] then uid[1] (different context) then uid[2] (same context as uid[0])
        # uid[2] must land immediately after uid[0], not after uid[1]
        reset_annotation()
        sid, session = add_files_to_session(signers, (self.uids[0],))[-1]
        sid, session = add_files_to_session(signers, (self.uids[1],), session_id=sid)[-1]
        sid, session = add_files_to_session(signers, (self.uids[2],), session_id=sid)[-1]
        self.assertEqual([f["uid"] for f in session["files"]], [self.uids[0], self.uids[2], self.uids[1]])

        # Case 2: uid[4] (3rd in folder0) added before uid[0] (1st in folder0)
        # uid[0] must land before uid[4]
        reset_annotation()
        sid, session = add_files_to_session(signers, (self.uids[4],))[-1]
        sid, session = add_files_to_session(signers, (self.uids[0],), session_id=sid)[-1]
        self.assertEqual([f["uid"] for f in session["files"]], [self.uids[0], self.uids[4]])

        # Case 3: uid[0], uid[4] in session, then uid[1] (different context), then uid[2]
        # uid[2] must be inserted between uid[0] and uid[4]
        reset_annotation()
        sid, session = add_files_to_session(signers, (self.uids[0],))[-1]
        sid, session = add_files_to_session(signers, (self.uids[4],), session_id=sid)[-1]
        sid, session = add_files_to_session(signers, (self.uids[1],), session_id=sid)[-1]
        sid, session = add_files_to_session(signers, (self.uids[2],), session_id=sid)[-1]
        self.assertEqual(
            [f["uid"] for f in session["files"]],
            [self.uids[0], self.uids[2], self.uids[4], self.uids[1]],
        )

    def test_remove_files_from_session(self):
        """remove_files_from_session: partial removal keeps session; removing last file deletes it."""
        signers = [
            ("user1", "user1@sign.com", "User 1", "Position 1"),
            ("user2", "user2@sign.com", "User 2", "Position 2"),
        ]
        annot = get_session_annotation()
        add_files_to_session(signers, (self.uids[0], self.uids[1], self.uids[2]))

        # --- partial removal: 2 of 3 files ---
        remove_files_from_session((self.uids[0], self.uids[1]))
        self.assertEqual(len(annot["uids"]), 1)
        self.assertEqual(len(annot["sessions"][0]["files"]), 1)
        self.assertEqual(annot["sessions"][0]["size"], 6968)  # only uids[2] (annex1.pdf) remains

        # --- remove last file: session deleted ---
        remove_files_from_session((self.uids[2],))
        self.assertEqual(len(annot["uids"]), 0)
        self.assertEqual(len(annot["sessions"]), 0)

        # --- remove_empty_session=False: session kept with empty files list ---
        add_files_to_session(signers, (self.uids[0],))
        session_id = annot["uids"][self.uids[0]]
        remove_files_from_session((self.uids[0],), remove_empty_session=False)
        self.assertEqual(len(annot["uids"]), 0)
        self.assertEqual(len(annot["sessions"]), 1)
        self.assertEqual(annot["sessions"][session_id]["files"], [])

    def test_get_filesize(self):
        """get_filesize: reads cached value from categorized_elements, falls back to blob."""
        self.assertEqual(get_filesize(self.uids[0]), 6968)  # annex0 uses annex1.pdf (6968 bytes)
        self.assertEqual(get_filesize(self.uids[1]), 7014)  # annex1 uses annex2.pdf (7014 bytes)
        self.assertEqual(get_filesize("nonexistent_uid"), 0)

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

    def test_remove_context_from_session(self):
        """remove_context_from_session: removes all files for a context UID; deletes session when empty."""
        signers = [
            ("user1", "user1@sign.com", "User 1", "Position 1"),
            ("user2", "user2@sign.com", "User 2", "Position 2"),
        ]
        annot = get_session_annotation()
        self.assertEqual(len(annot["sessions"]), 0)
        add_files_to_session(signers, (self.uids[0], self.uids[1], self.uids[2], self.uids[3]))
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
        """remove_session: deletes the session and clears its file UID references."""
        signers = [
            ("user1", "user1@sign.com", "User 1", "Position 1"),
            ("user2", "user2@sign.com", "User 2", "Position 2"),
        ]
        annot = get_session_annotation()
        self.assertEqual(len(annot["sessions"]), 0)
        add_files_to_session(signers, (self.uids[0], self.uids[1]))
        sid2, _session = add_files_to_session(signers, (self.uids[2], self.uids[3]), seal="seal1")[-1]
        self.assertEqual(sid2, 1)
        remove_session(0)
        self.assertEqual(len(annot["uids"]), 2)
        self.assertEqual(len(annot["c_uids"]), 2)
        self.assertEqual(len(annot["sessions"]), 1)

    def test_get_session_info(self):
        """get_session_info: returns {} for unknown id; returns session dict for known id."""
        annot = get_session_annotation()
        self.assertEqual(len(annot["sessions"]), 0)
        self.assertEqual(get_session_info(0), {})
        self.assertEqual(get_session_info(1), {})
        self.assertEqual(get_session_info(2), {})
        signers = [
            ("user1", "user1@sign.com", "User 1", "Position 1"),
            ("user2", "user2@sign.com", "User 2", "Position 2"),
        ]
        sid, session = add_files_to_session(signers, (self.uids[0], self.uids[1]))[-1]
        self.assertEqual(get_session_info(sid), session)

    def test_get_sessions_for(self):
        """get_sessions_for: returns OrderedDict keyed by session id; honours readonly flag."""
        context_uid = self.folders[0].UID()
        self.assertEqual(get_sessions_for(context_uid), OrderedDict())

        signers = [("user1", "user1@sign.com", "User 1", "Position 1")]
        add_files_to_session(signers, (self.uids[0],))
        self.assertEqual(list(get_sessions_for(context_uid).keys()), [0])

        signers2 = [("user2", "user2@sign.com", "User 2", "Position 2")]
        add_files_to_session(signers2, (self.uids[2],))
        self.assertEqual(list(get_sessions_for(context_uid).keys()), [0, 1])

        # One item belonging to multiple sessions
        annot = get_session_annotation()
        annot["sessions"][0]["state"] = "to_sign"
        new_id, _new = create_session(signers, annot=annot, title=u"")
        add_files_to_session(signers, (self.uids[0],), session_id=new_id)
        result = get_sessions_for(context_uid)
        self.assertIn(0, result)
        self.assertIn(1, result)
        self.assertIn(new_id, result)
        self.assertEqual(len(result), 3)

        # readonly=True (default): mutations do not persist
        sessions = get_sessions_for(context_uid)
        self.assertEqual(get_session_info(0)["watchers"], [])
        sessions[0]["watchers"] = ["watcher@sign.com"]
        self.assertEqual(get_session_info(0)["watchers"], [])

        # readonly=False: mutations persist
        sessions = get_sessions_for(context_uid, readonly=False)
        self.assertEqual(get_session_info(0)["watchers"], [])
        sessions[0]["watchers"] = ["watcher@sign.com"]
        self.assertEqual(get_session_info(0)["watchers"], ["watcher@sign.com"])

    def test_get_file_info(self):
        """get_file_info: returns None for unknown session/file; honours readonly flag."""
        annex0_uid = self.uids[0]
        annex1_uid = self.uids[1]
        self.assertIsNone(get_file_info(0, annex0_uid))

        signers = [("user1", "user1@sign.com", "User 1", "Position 1")]
        add_files_to_session(signers, (annex0_uid,))
        self.assertEqual(get_file_info(0, annex0_uid)["uid"], annex0_uid)
        self.assertIsNone(get_file_info(0, annex1_uid))

        # readonly=True: mutations do not persist
        file_info = get_file_info(0, annex0_uid)
        file_info["title"] = u"New title annex 0"
        self.assertEqual(get_session_annotation()["sessions"][0]["files"][0]["title"], u"Annex 0")

        # readonly=False: mutations persist
        file_info = get_file_info(0, annex0_uid, readonly=False)
        file_info["title"] = u"New title annex 0"
        self.assertEqual(get_session_annotation()["sessions"][0]["files"][0]["title"], u"New title annex 0")

    def test_get_file_download_url(self):
        """get_file_download_url: encodes UID; respects custom root_url; accepts pre-computed short_uid."""
        uid = "f40682caafc045b4b81973bd82ea9ab6"
        api.portal.set_registry_record("imio.esign.file_url", "https://downloads.files.com")

        result = get_file_download_url(uid)
        self.assertEqual(
            result, ("https://downloads.files.com/Rzgwy-9BVG9-viEts-5GBkn-Rm", "Rzgwy-9BVG9-viEts-5GBkn-Rm")
        )

        custom_url = "https://custom.domain.org/"
        result = get_file_download_url(uid, root_url=custom_url)
        self.assertEqual(result[0], "https://custom.domain.org/Rzgwy-9BVG9-viEts-5GBkn-Rm")

        uid2 = self.uids[0]
        result2 = get_file_download_url(uid2)
        self.assertTrue(result2[0].startswith("https://downloads.files.com/"))
        self.assertEqual(shortuid_decode_id(result2[1], separator="-"), uid2)

        result3 = get_file_download_url(None, short_uid="MyCustom-Short-UID")
        self.assertEqual(result3, ("https://downloads.files.com/MyCustom-Short-UID", "MyCustom-Short-UID"))

    def test_get_max_download_date(self):
        annex = self.folders[0]
        mod_date = annex.modified().asdatetime().date()
        self.assertEqual(get_max_download_date(annex), mod_date + timedelta(days=90))
        self.assertEqual(get_max_download_date(annex, timedelta(days=0)), mod_date)
        today = date.today()
        self.assertEqual(get_max_download_date(None, timedelta(days=0), today), today)

    def test_create_external_session(self):
        """create_external_session: validates state, seal config, file resolution, and builds payloads."""
        signers = [("user1", "user1@sign.com", "User 1", "Position 1")]

        # --- session not found ---
        result = create_external_session(9999)
        self.assertEqual(result, "_session_not_found_")

        # --- seal session: email missing ---
        sid, _session = add_files_to_session([], (self.uids[0],), seal="SEAL")[-1]
        result = create_external_session(sid, esign_root_url="http://test.example.com")
        self.assertEqual(result, "_no_seal_email_")

        # --- seal session: code missing ---
        api.portal.set_registry_record("imio.esign.seal_email", u"seal@example.com")
        self.addCleanup(api.portal.set_registry_record, "imio.esign.seal_email", u"")
        result = create_external_session(sid, esign_root_url="http://test.example.com")
        self.assertEqual(result, "_no_seal_code_")

        # --- error response: state unchanged ---
        sid2, session2 = add_files_to_session(signers, (self.uids[1],))[-1]
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        with patch("imio.esign.utils.requests.post", return_value=mock_response):  # real HTTP call
            with patch("imio.esign.utils.get_auth_token", return_value="test-token"):  # remote OAuth
                result = create_external_session(sid2, esign_root_url="http://test.example.com")
        self.assertIs(result, mock_response)
        self.assertEqual(session2["state"], "draft")

        # --- sign payload: correct structure, state set to 'sent' ---
        sid3, session3 = add_files_to_session(signers, (self.uids[2],))[-1]
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = '{"message": "OK"}'
        with patch("imio.esign.utils.requests.post", return_value=mock_response) as mock_post:  # real HTTP call
            with patch("imio.esign.utils.get_auth_token", return_value="test-token"):  # remote OAuth
                result = create_external_session(sid3, esign_root_url="http://test.example.com")
        self.assertIs(result, mock_response)
        self.assertEqual(session3["state"], "sent")
        payload = json.loads(mock_post.call_args[1]["data"]["data"])
        posted_files = mock_post.call_args[1]["files"]
        self.assertIsInstance(posted_files, list)
        self.assertEqual([f[0] for f in posted_files], ["files", "files"])
        self.assertEqual([f[1][0] for f in posted_files], [u"annex1.pdf", u"annex2.pdf"])
        self.assertEqual(
            payload,
            {
                u"commonData": {
                    u"imioAppSessionId": u"012345600001",
                    u"vatNumber": None,
                    u"endpointUrl": u"http://nohost/plone/@external_session_feedback",
                    u"sessionName": u"Session {}".format(sid3),
                    u"documentData": [
                        {
                            u"uniqueCode": u"012345600000001__{}".format(self.uids[1]),
                            u"docUuid": get_suid_from_uuid(self.uids[1]),
                            u"filename": u"annex1.pdf",
                        },
                        {
                            u"uniqueCode": u"012345600000002__{}".format(self.uids[2]),
                            u"docUuid": get_suid_from_uuid(self.uids[2]),
                            u"filename": u"annex2.pdf",
                        },
                    ],
                },
                u"signData": {u"acroform": True, u"users": [u"user1@sign.com"]},
            },
        )

        # --- seal-only payload ---
        api.portal.set_registry_record("imio.esign.seal_code", u"PADES_SEAL")
        self.addCleanup(api.portal.set_registry_record, "imio.esign.seal_code", u"")
        sid4, _session = add_files_to_session([], (self.uids[3],), seal="SEAL")[-1]
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = '{"message": "OK"}'
        with patch("imio.esign.utils.requests.post", return_value=mock_response) as mock_post:  # real HTTP call
            with patch("imio.esign.utils.get_auth_token", return_value="test-token"):  # remote OAuth
                create_external_session(sid4, esign_root_url="http://test.example.com")
        self.assertEqual(mock_post.call_args[0][0], "http://test.example.com/imio/esign/v1/luxtrust/sessions")
        payload = json.loads(mock_post.call_args[1]["data"]["data"])
        self.assertEqual(
            payload,
            {
                u"commonData": {
                    u"imioAppSessionId": u"012345600000",
                    u"vatNumber": None,
                    u"endpointUrl": u"http://nohost/plone/@external_session_feedback",
                    u"sessionName": u"Session {}".format(sid4),
                    u"documentData": [
                        {
                            u"uniqueCode": u"012345600000000__{}".format(self.uids[0]),
                            u"docUuid": get_suid_from_uuid(self.uids[0]),
                            u"filename": u"annex0.pdf",
                        },
                        {
                            u"uniqueCode": u"012345600000003__{}".format(self.uids[3]),
                            u"docUuid": get_suid_from_uuid(self.uids[3]),
                            u"filename": u"annex3.pdf",
                        },
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
        posted_files = mock_post.call_args[1]["files"]
        self.assertIsInstance(posted_files, list)
        self.assertEqual([f[0] for f in posted_files], ["files", "files"])
        self.assertEqual([f[1][0] for f in posted_files], [u"annex0.pdf", u"annex3.pdf"])

        # --- combined sign + seal payload ---
        sid5, _session = add_files_to_session(signers, (self.uids[4],), seal="SEAL")[-1]
        set_esign_registry_external_watchers(u"example@imlo.be")
        self.addCleanup(set_esign_registry_external_watchers, u"")
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = '{"message": "OK"}'
        with patch("imio.esign.utils.requests.post", return_value=mock_response) as mock_post:  # real HTTP call
            with patch("imio.esign.utils.get_auth_token", return_value="test-token"):  # remote OAuth
                create_external_session(sid5, esign_root_url="http://test.example.com")
        payload = json.loads(mock_post.call_args[1]["data"]["data"])
        self.assertEqual(
            payload,
            {
                u"signData": {
                    u"acroform": True,
                    u"users": [u"user1@sign.com"],
                    u"watchers": [u"example@imlo.be"],
                },
                u"commonData": {
                    u"imioAppSessionId": u"012345600002",
                    u"vatNumber": None,
                    u"endpointUrl": u"http://nohost/plone/@external_session_feedback",
                    u"sessionName": u"Session {}".format(sid5),
                    u"documentData": [
                        {
                            u"uniqueCode": u"012345600000004__{}".format(self.uids[4]),
                            u"docUuid": get_suid_from_uuid(self.uids[4]),
                            u"filename": u"annex4.pdf",
                        }
                    ],
                },
                u"sealData": {
                    u"sealCode": u"PADES_SEAL",
                    u"acroform": True,
                    u"users": [u"seal@example.com"],
                    u"watchers": [u"example@imlo.be"],
                },
            },
        )
        posted_files = mock_post.call_args[1]["files"]
        self.assertIsInstance(posted_files, list)
        self.assertEqual([f[0] for f in posted_files], ["files"])
        self.assertEqual([f[1][0] for f in posted_files], [u"annex4.pdf"])

        # --- no resolvable files: returns _no_files_, no HTTP call made ---
        sid6, session6 = add_files_to_session(signers, (self.uids[5],))[-1]
        for i in range(len(session6["files"])):
            session6["files"][i]["uid"] = "nonexistent_uid_{}".format(i)
        with patch("imio.esign.utils.get_auth_token", return_value="test-token"):  # remote OAuth
            with patch(
                "imio.esign.utils.requests"
            ) as mock_requests:  # real HTTP call; whole module patched to assert .post not called
                result = create_external_session(sid6, esign_root_url="http://test.example.com")
        self.assertEqual(result, "_no_files_")
        mock_requests.post.assert_not_called()
