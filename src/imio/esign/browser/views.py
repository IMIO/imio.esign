# -*- coding: utf-8 -*-
from collective.eeafaceted.dashboard.browser.overrides import DashboardFacetedTableView
from imio.esign import _
from imio.esign.browser.table import SessionsTable
from imio.helpers.content import uuidToObject
from imio.prettylink.interfaces import IPrettyLink
from Products.Five import BrowserView
from zope.browserpage.viewpagetemplatefile import ViewPageTemplateFile
from zope.i18n import translate


DUMMY_SESSIONS = [
    {
        "id": 12554,
        "state": "open",
        "title": "Session 1",
        "last_update": "2023-10-01",
        "signers": [
            {"name": "Alice Dupont", "status": "signed"},
            {"name": "Bob Dupont", "status": "pending"},
        ],
        "documents": [
            {"title": "CV Informaticien N°2016-2", "uid": "78e72614568f4e8cb74a7fda90f89ad1"},
            {"title": "CV Informaticien N°2016-3", "uid": "bef0c3f2f4474d31b41a382950825582"},
            {"title": "CV Informaticien N°2016-4", "uid": "f02fd69975e644f0867d599135c1ff8e"},
        ],
    },
    {
        "id": 12555,
        "state": "closed",
        "title": "Session 2",
        "last_update": "2023-10-05",
        "signers": [
            {"name": "Jean Dupont", "status": "signed"},
            {"name": "Paul Dupont", "status": "signed"},
        ],
        "documents": [
            {"title": "CV Informaticien N°2016-2", "uid": "78e72614568f4e8cb74a7fda90f89ad1"},
        ],
    },
    {
        "id": 12556,
        "state": "pending",
        "title": "Session 3",
        "last_update": "2023-10-07",
        "signers": [
            {"name": "Eve Dupont", "status": "pending"},
            {"name": "Frank Dupont", "status": "pending"},
        ],
        "documents": [],
    },
    {
        "id": 12557,
        "state": "open",
        "title": "Session 4",
        "last_update": "2023-10-09",
        "signers": [
            {"name": "Grace Dupont", "status": "signed"},
            {"name": "Heidi Dupont", "status": "pending"},
            {"name": "Ivan Dupont", "status": "signed"},
        ],
        "documents": [
            {"title": "CV Informaticien N°2016-2", "uid": "78e72614568f4e8cb74a7fda90f89ad1"},
            {"title": "CV Informaticien N°2016-3", "uid": "bef0c3f2f4474d31b41a382950825582"},
            {"title": "CV Informaticien N°2016-4", "uid": "f02fd69975e644f0867d599135c1ff8e"},
        ],
    },
    {
        "id": 12558,
        "state": "closed",
        "title": "Session 5",
        "last_update": "2023-10-12",
        "signers": [{"name": "Judy Dupont", "status": "signed"}],
        "documents": [
            {"title": "CV Informaticien N°2016-2", "uid": "78e72614568f4e8cb74a7fda90f89ad1"},
            {"title": "CV Informaticien N°2016-3", "uid": "bef0c3f2f4474d31b41a382950825582"},
            {"title": "CV Informaticien N°2016-4", "uid": "f02fd69975e644f0867d599135c1ff8e"},
            {"title": "CV Informaticien N°2016-2", "uid": "78e72614568f4e8cb74a7fda90f89ad1"},
            {"title": "CV Informaticien N°2016-3", "uid": "bef0c3f2f4474d31b41a382950825582"},
            {"title": "CV Informaticien N°2016-4", "uid": "f02fd69975e644f0867d599135c1ff8e"},
        ],
    },
]


class SessionsListingView(BrowserView):
    """View to list sessions."""

    index = ViewPageTemplateFile("templates/sessions.pt")

    def __init__(self, context, request):
        super(SessionsListingView, self).__init__(context, request)

    def __call__(self):
        return self.index()

    def render_table(self, table_class=None, contents=None):
        """Render a z3c.table for sessions."""
        items = contents if contents is not None else self.get_sessions()
        table = SessionsTable(self.context, self.request, items)
        table.update()
        return table.render()

    def get_sessions(self):
        return DUMMY_SESSIONS


class SessionDashboardView(DashboardFacetedTableView):
    """View to display a single session."""

    index = ViewPageTemplateFile("templates/session.pt")

    def __init__(self, context, request):
        # TODO handle a session ID URL parameter to fetch the session
        # Handle not found session gracefully
        super(SessionDashboardView, self).__init__(context, request)

    def __call__(self):
        return self.index()

    def _set_collection(self):
        return uuidToObject("")


class SessionDocumentsView(BrowserView):
    """View to display documents of a session."""

    index = ViewPageTemplateFile("templates/session_documents.pt")

    def __init__(self, context, request):
        super(SessionDocumentsView, self).__init__(context, request)
        self.documents = []

    def __call__(self):
        session_id = self.request.get("session_id")
        session = filter(lambda s: str(s.get("id")) == session_id, DUMMY_SESSIONS)
        uids = [doc["uid"] for doc in session[0].get("documents", []) if doc.get("uid")] if session else []
        objs = []
        for uid in uids:
            try:
                obj = uuidToObject(uid)
                objs.append(obj)
            except Exception:
                continue
        self.documents = objs
        return self.index()

    def get_documents(self):
        """List of document objects."""
        return self.documents

    def get_no_documents_label(self):
        return translate(_("No documents"), context=self.request)

    def get_document_link(self, obj):
        return IPrettyLink(obj.aq_parent).getLink() + " / " + IPrettyLink(obj).getLink()
