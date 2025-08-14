# -*- coding: utf-8 -*-
import datetime
import pprint

from Products.CMFPlone.utils import safe_unicode
from imio.esign import _
from imio.esign.browser.table import SessionsTable
from imio.helpers.content import uuidToObject
from imio.prettylink.interfaces import IPrettyLink
from Products.Five import BrowserView
from plone import api
from zope.browserpage.viewpagetemplatefile import ViewPageTemplateFile
from zope.i18n import translate
from plone.app.layout.viewlets import ViewletBase

DUMMY_SESSIONS = {
    "numbering": 1,
    "uids": {"78e72614568f4e8cb74a7fda90f89ad1": 0},
    "sessions": {
        25452: {
            "id": 25452,
            "files": [
                {
                    "scan_id": "012345600000001",
                    "title": "Annex 1",
                    "uid": "78e72614568f4e8cb74a7fda90f89ad1",
                    "context_uid": "c65197e2bab64ceab88c405dc0296cfa",
                    "filename": "annex1.pdf",
                }
            ],
            "title": "Séance du Collège du 13/08/2025 (18:00) - 1",
            "signers": [
                {
                    "status": "pending",
                    "userid": "user1",
                    "fullname": "Jean Dupont",
                    "held_position": u"Directeur Général",
                    "email": "user1@sign.com",
                },
                {
                    "status": "signed",
                    "userid": "user2",
                    "fullname": "Jeanne Dupont",
                    "held_position": u"Bourgmestre",
                    "email": "user2@sign.com",
                },
            ],
            "last_update": datetime.datetime(2025, 8, 13, 10, 44, 1, 419579),
            "state": "draft",
            "seal": False,
        },
        25453: {
            "id": 25453,
            "files": [
                {
                    "scan_id": "012345600000001",
                    "title": "Annex 1",
                    "uid": "78e72614568f4e8cb74a7fda90f89ad1",
                    "context_uid": "c65197e2bab64ceab88c405dc0296cfa",
                    "filename": "annex1.pdf",
                }
            ],
            "title": "Séance du Collège du 18/08/2025 (18:00) - 1",
            "signers": [
                {
                    "status": "pending",
                    "userid": "user1",
                    "fullname": "Jean Dupont",
                    "held_position": u"Directeur Général",
                    "email": "user1@sign.com",
                },
                {
                    "status": "signed",
                    "userid": "user2",
                    "fullname": "Jeanne Dupont",
                    "held_position": u"Bourgmestre",
                    "email": "user2@sign.com",
                },
            ],
            "last_update": datetime.datetime(2025, 8, 13, 10, 44, 1, 419579),
            "state": "draft",
            "seal": False,
        },
        25454: {
            "id": 25454,
            "files": [
                {
                    "scan_id": "012345600000001",
                    "title": "Annex 1",
                    "uid": "78e72614568f4e8cb74a7fda90f89ad1",
                    "context_uid": "c65197e2bab64ceab88c405dc0296cfa",
                    "filename": "annex1.pdf",
                }
            ],
            "title": "Séance du Collège du 18/08/2025 (18:00) - 2",
            "signers": [
                {
                    "status": "pending",
                    "userid": "user1",
                    "fullname": "Jean Dupont",
                    "held_position": u"Directeur Général",
                    "email": "user1@sign.com",
                },
                {
                    "status": "signed",
                    "userid": "user2",
                    "fullname": "Jeanne Dupont",
                    "held_position": u"Bourgmestre",
                    "email": "user2@sign.com",
                },
            ],
            "last_update": datetime.datetime(2025, 8, 13, 10, 44, 1, 419579),
            "state": "draft",
            "seal": False,
        },
    },
}


class SessionsListingView(BrowserView):
    """View to list sessions."""

    index = ViewPageTemplateFile("templates/sessions.pt")

    def __init__(self, context, request):
        super(SessionsListingView, self).__init__(context, request)

    def __call__(self):
        return self.index()

    def render_table(self):
        table = SessionsTable(self.context, self, self.request, self.get_sessions())
        table.update()
        return table.render()

    def get_sessions(self):
        return DUMMY_SESSIONS["sessions"].values()

    def get_dashboard_link(self, session):
        user_id = api.user.get_current().getId()
        return "Members/{user_id}/mymeetings/meeting-config-college/searches_items#c3=20&b_start=0&c1={collection_uid}&esign_session_id={session_id}".format(
            user_id=user_id,
            collection_uid="a25665fc111f48da99674b893ba60ed9",
            session_id=session["id"],
        )


class SessionFilesView(BrowserView):
    """View to display documents of a session."""

    index = ViewPageTemplateFile("templates/session_files.pt")

    def __init__(self, context, request):
        super(SessionFilesView, self).__init__(context, request)
        self.files = []

    def __call__(self):
        session_id = self.request.get("session_id")
        session = self.get_session(session_id)
        files = []
        for f in session["files"]:
            ctx = uuidToObject(f["context_uid"])
            obj = uuidToObject(f["uid"])
            if obj and ctx:
                files.append((ctx, obj))
        self.files = files
        return self.index()

    def get_session(self, session_id):
        """Get the session object."""
        return filter(lambda s: s["id"] == int(session_id), DUMMY_SESSIONS["sessions"].values())[0]

    def get_file_link(self, ctx, obj):
        return IPrettyLink(ctx).getLink() + " / " + IPrettyLink(obj).getLink()

class FacetedSessionSessionInfoViewlet(ViewletBase):
    """Show selected session info inside faceted results."""

    # Put the template in your package under: imio/esign/browser/templates/faceted_session_info.pt
    index = ViewPageTemplateFile("templates/faceted_session_info.pt")

    @property
    def available(self):
        #TODO: when no esign_session_id, display the sessions listing view
        return "esign_session_id[]" in self.request.form.keys()


    def update(self):
        super(FacetedSessionSessionInfoViewlet, self).update()
        self.session = None
        if "esign_session_id[]" in self.request.form.keys():
            session_id = self.request.form["esign_session_id[]"]
        else:
            session_id = self.request.get("esign_session_id", None)
        if not session_id:
            return
        data = DUMMY_SESSIONS.get('sessions', {})
        sess = data.get(int(session_id))
        if not sess:
            return
        self.session = sess

    def has_session(self):
        return bool(self.session)