# -*- coding: utf-8 -*-
"""events tests for this package."""
from imio.esign.tests.base import BaseEsignTest
from imio.esign.utils import add_files_to_session
from zope.event import notify
from zope.lifecycleevent import ObjectModifiedEvent


class TestEvents(BaseEsignTest):
    def test_on_categorized_annex_updated(self):
        """Renaming an annex keeps its session filename unique, without conflicting with itself."""
        signers = [("user1", "user1@sign.com", "User 1", "Position 1")]
        annex0 = self.portal["folder0"]["annex0"]
        annex2 = self.portal["folder0"]["annex2"]
        sid, session = add_files_to_session(signers, (annex0.UID(), annex2.UID()))[-1]
        self.assertEqual([f["filename"] for f in session["files"]], [u"annex0.pdf", u"annex2.pdf"])
        # renamed to a name already used in the session: deduplicated
        annex2.file.filename = u"annex0.pdf"
        notify(ObjectModifiedEvent(annex2))
        self.assertEqual([f["filename"] for f in session["files"]], [u"annex0.pdf", u"annex0-1.pdf"])
        # updated again: the generated name is the one it already has, it must not drift to annex0-2.pdf
        annex2.setTitle("New Annex 2")
        notify(ObjectModifiedEvent(annex2))
        self.assertEqual([f["filename"] for f in session["files"]], [u"annex0.pdf", u"annex0-1.pdf"])
        self.assertEqual(session["files"][1]["title"], "New Annex 2")
