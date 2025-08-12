# -*- coding: utf-8 -*-
from Products.Five import BrowserView
from collective.eeafaceted.dashboard.browser.overrides import DashboardFacetedTableView
from imio.helpers.content import uuidToObject
from imio.prettylink.interfaces import IPrettyLink
from plone import api
from plone.dexterity.utils import safe_unicode
from zope.browserpage.viewpagetemplatefile import ViewPageTemplateFile
from z3c.table.table import Table
from z3c.table.column import Column
from zope.component import getMultiAdapter
from zope.i18n import translate
from imio.esign import _

DUMMY_SESSIONS = [
    {
        'id': 12554,
        'state': 'open',
        'title': 'Session 1',
        'last_update': '2023-10-01',
        'signers': [
            {'name': 'Alice Dupont', 'status': 'signed'},
            {'name': 'Bob Dupont', 'status': 'pending'},
        ],
        'documents': [
                         {"title": "CV Informaticien N°2016-2", "uid": "78e72614568f4e8cb74a7fda90f89ad1"},
                         {"title": "CV Informaticien N°2016-3", "uid": "bef0c3f2f4474d31b41a382950825582"},
                         {"title": "CV Informaticien N°2016-4", "uid": "f02fd69975e644f0867d599135c1ff8e"},
                     ]
    },
    {
        'id': 12555,
        'state': 'closed',
        'title': 'Session 2',
        'last_update': '2023-10-05',
        'signers': [
            {'name': 'Jean Dupont', 'status': 'signed'},
            {'name': 'Paul Dupont', 'status': 'signed'},
        ],
        'documents': [
            {"title": "CV Informaticien N°2016-2", "uid": "78e72614568f4e8cb74a7fda90f89ad1"},
        ]
    },
    {
        'id': 12556,
        'state': 'pending',
        'title': 'Session 3',
        'last_update': '2023-10-07',
        'signers': [
            {'name': 'Eve Dupont', 'status': 'pending'},
            {'name': 'Frank Dupont', 'status': 'pending'},
        ],
        'documents': []
    },
    {
        'id': 12557,
        'state': 'open',
        'title': 'Session 4',
        'last_update': '2023-10-09',
        'signers': [
            {'name': 'Grace Dupont', 'status': 'signed'},
            {'name': 'Heidi Dupont', 'status': 'pending'},
            {'name': 'Ivan Dupont', 'status': 'signed'},
        ],
        'documents': [
            {"title": "CV Informaticien N°2016-2", "uid": "78e72614568f4e8cb74a7fda90f89ad1"},
            {"title": "CV Informaticien N°2016-3", "uid": "bef0c3f2f4474d31b41a382950825582"},
            {"title": "CV Informaticien N°2016-4", "uid": "f02fd69975e644f0867d599135c1ff8e"},
        ]
    },
    {
        'id': 12558,
        'state': 'closed',
        'title': 'Session 5',
        'last_update': '2023-10-12',
        'signers': [
            {'name': 'Judy Dupont', 'status': 'signed'}
        ],
        'documents': [
            {"title": "CV Informaticien N°2016-2", "uid": "78e72614568f4e8cb74a7fda90f89ad1"},
            {"title": "CV Informaticien N°2016-3", "uid": "bef0c3f2f4474d31b41a382950825582"},
            {"title": "CV Informaticien N°2016-4", "uid": "f02fd69975e644f0867d599135c1ff8e"},
            {"title": "CV Informaticien N°2016-2", "uid": "78e72614568f4e8cb74a7fda90f89ad1"},
            {"title": "CV Informaticien N°2016-3", "uid": "bef0c3f2f4474d31b41a382950825582"},
            {"title": "CV Informaticien N°2016-4", "uid": "f02fd69975e644f0867d599135c1ff8e"},
        ]
    },
]


class IdColumn(Column):
    header = _("ID")
    weight = 10

    def renderCell(self, item):
        return str(item.get("id", ""))


class StateColumn(Column):
    header = _("State")
    weight = 20

    def renderCell(self, item):
        return translate((item.get("state", "")), context=self.request, default=item.get("state", ""), domain="plone")


class TitleColumn(Column):
    header = _("Title")
    weight = 30

    def renderCell(self, item):
        return item.get("title", "")


class LastUpdateColumn(Column):
    header = _("Last update")
    weight = 40

    def renderCell(self, item):
        return item.get("last_update", "")


class SignersColumn(Column):
    header = _("Signers")
    weight = 50

    def renderCell(self, item):
        signers = item.get("signers") or []
        parts = ["<li>%s (%s)</li>" % (s.get('name', ''), s.get('status', '')) for s in signers]
        return "<ol>%s</ol>" % "".join(parts)


class DocumentsColumn(Column):
    header = _("Documents")
    weight = 60
    cssClasses = {'td': 'documents-column'}

    def renderCell(self, item):
        """Render a collapsible block that loads the document list on demand."""
        # Row identifier (unique per session)
        session_id = item.get('id')

        # Text for the clickable area (translated like your example)
        details_msg = translate(_(u"Aperçu"), context=self.request)

        # Where the loader fetches from.
        # Keep the same pattern as your example: base_url + spinner path, and
        # an @@ view that returns the rendered list for the given UUIDs.
        base_url = getattr(self.table, 'portal_url', None)
        if not base_url:
            # very safe fallback
            try:
                base_url = self.context.absolute_url()
            except Exception:
                base_url = u""

        # TODO: Refactor this
        html = (
            u"<div id=\"session-docs\" class=\"collapsible\" "
            u"onclick=\"toggleDetails('collapsible-session-docs_{0}', "
            u"toggle_parent_active=true, parent_tag=null, "
            u"load_view='@@esign-session-documents?session_id={0}', "
            u"base_url='{2}');\"> {3}</div>"
            u"<div id=\"collapsible-session-docs_{0}\" class=\"collapsible-content\" style=\"display: none;\">"
            u"<div class=\"collapsible-inner-content\">"
            u"<img src=\"{3}/spinner_small.gif\" />"
            u"</div></div>"
            """<a target="_parent" href="@@esign-session?session_id={0}" style="margin-top: 6px;">
                    <img class="categorized_elements_more_infos_icon" src="http://localhost:8081/Plone/++resource++collective.iconifiedcategory.images/more_infos.png">
                    <span>Tableau de bord</span>
                  </a>"""
        ).format(session_id, base_url, details_msg)

        return html


class ActionsColumn(Column):
    """
    A column displaying available actions of the listed item.
    Requires imio.actionspanel if the row item is a real content object.
    With mocked dict rows, we gracefully fall back to empty output.
    """
    header = _(u"Actions")
    weight = 70
    params = {
        'useIcons': True, 'showHistory': False, 'showActions': True,
        'showOwnDelete': False, 'showArrows': True, 'showTransitions': False,
        'showExtEdit': True, 'edit_action_class': 'dg_edit_action',
        'edit_action_target': '_blank',
    }
    cssClasses = {'td': 'actions-column'}

    def renderCell(self, item):
        return u""


class SessionsTable(Table):
    cssClassEven = u'even'
    cssClassOdd = u'odd'
    cssClasses = {'table': 'listing nosort sessions-table width-full'}

    # ?table-batchSize=10&table-batchStart=30
    batchSize = 200
    startBatchingAt = 200
    sortOn = None
    results = []

    def __init__(self, context, request, items=None):
        super(SessionsTable, self).__init__(context, request)
        self._items = items

    @property
    def values(self):
        # z3c.table reads from this; must be iterable of row items (dicts here)
        return self._items

    def setUpColumns(self):
        ctx, req, tbl = self.context, self.request, self
        return [
            IdColumn(ctx, req, tbl),
            StateColumn(ctx, req, tbl),
            TitleColumn(ctx, req, tbl),
            LastUpdateColumn(ctx, req, tbl),
            SignersColumn(ctx, req, tbl),
            DocumentsColumn(ctx, req, tbl),
            ActionsColumn(ctx, req, tbl),
        ]


class SessionsListingView(BrowserView):
    """View to list sessions."""
    index = ViewPageTemplateFile('templates/sessions.pt')

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
    index = ViewPageTemplateFile('templates/session.pt')

    def __init__(self, context, request):
        # TODO handle a session ID URL parameter to fetch the session
        # Handle not found session gracefully
        super(SessionDashboardView, self).__init__(context, request)

    def __call__(self):
        return self.index()

    def _set_collection(self):
        return uuidToObject("")


    def get_session(self):
        return {
            'id': 12554,
            'state': 'open',
            'title': 'Session 1',
            'last_update': '2023-10-01',
            'signers': [
                {'name': 'Alice Dupont', 'status': 'signed'},
                {'name': 'Bob Dupont', 'status': 'pending'},
            ],
            'documents': [
                "78e72614568f4e8cb74a7fda90f89ad1",
                "bef0c3f2f4474d31b41a382950825582",
                "f02fd69975e644f0867d599135c1ff8e",
            ]
        }


class SessionDocumentsView(BrowserView):
    """View to display documents of a session."""
    index = ViewPageTemplateFile('templates/session_documents.pt')

    def __init__(self, context, request):
        super(SessionDocumentsView, self).__init__(context, request)
        self.documents = []
        self._icon_cache = {}  # portal_type -> img html

    def __call__(self):
        session_id = self.request.get('session_id')
        session = filter(lambda s: str(s.get('id')) == session_id, DUMMY_SESSIONS)
        uids = [doc["uid"] for doc in session[0].get('documents', []) if doc.get("uid")] if session else []
        objs = []
        for uid in uids:
            try:
                obj = uuidToObject(uid)
            except Exception:
                obj = None
            if obj is not None:
                objs.append(obj)
        self.documents = objs
        return self.index()

    def get_documents(self):
        """List of document objects."""
        return self.documents

    def get_no_documents_label(self):
        return translate(_(u"No documents"), context=self.request)

    def get_document_link(self, obj):
        return IPrettyLink(obj.aq_parent).getLink() + " / " + IPrettyLink(obj).getLink()
