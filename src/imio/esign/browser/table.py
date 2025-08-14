# -*- coding: utf-8 -*-
from DateTime import DateTime
from imio.esign import _
from Products.CMFPlone.utils import safe_unicode
from z3c.table.column import Column
from z3c.table.table import Table
from zope.i18n import translate


class IdColumn(Column):
    header = _("ID")
    weight = 10

    def renderCell(self, item):
        return str(item.get("id", ""))


class StateColumn(Column):
    header = _("State")
    weight = 20

    def renderCell(self, item):
        return translate(
            (item.get("state", "")), context=self.request, default=item.get("state", ""), domain="imio.esign"
        )


class TitleColumn(Column):
    header = _("Title")
    weight = 30

    def renderCell(self, item):
        return safe_unicode(item.get("title", ""))


class LastUpdateColumn(Column):
    header = _("Last update")
    weight = 40

    def renderCell(self, item):
        last_update = item.get("last_update")
        return self.context.toLocalizedTime(DateTime(last_update), long_format=True)


class SignersColumn(Column):
    header = _("Signers")
    weight = 50

    def renderCell(self, item):
        signers = item.get("signers") or []
        parts = [
            "<li>%s, %s (%s)</li>" % (s.get("fullname", ""), s.get("held_position"), s.get("status", ""))
            for s in signers
        ]
        return "<ol>%s</ol>" % "".join(parts)


class FilesColumn(Column):
    header = _("Files")
    weight = 60
    cssClasses = {"td": "documents-column"}

    def renderCell(self, item):
        """Render a collapsible block that loads the list on demand."""
        # Row identifier (unique per session)
        session_id = item.get("id")
        details_msg = translate(_("Quick look"), context=self.request)
        base_url = getattr(self.table, "portal_url", None)
        if not base_url:
            try:
                base_url = self.context.absolute_url()
            except Exception:
                base_url = ""

        html = (
            u'<div id="session-files" class="collapsible" '
            u"onclick=\"toggleDetails('collapsible-session-files_{0}', "
            u"toggle_parent_active=true, parent_tag=null, "
            u"load_view='@@esign-session-files?session_id={0}', "
            u"base_url='{1}');\"> {2}</div>"
            u'<div id="collapsible-session-files_{0}" class="collapsible-content" style="display: none;">'
            u'<div class="collapsible-inner-content">'
            u'<img src="{1}/spinner_small.gif" />'
            u"</div></div>"
        ).format(session_id, base_url, details_msg)

        # Add a link to the dashboard
        dashboard_link = self.table.view.get_dashboard_link(item)
        if dashboard_link:
            html += (u"""<div class="dashboard-link"><a href="{0}">{1}</a></div>""").format(
                dashboard_link, translate(_("Go to dashboard"), context=self.request)
            )

        return html


class ActionsColumn(Column):
    """ """

    header = _("Actions")
    weight = 70
    cssClasses = {"td": "actions-column"}

    def renderCell(self, item):
        return """
        <img title="Supprimer" onclick="javascript:confirmDeleteObject(base_url='http://localhost:8081/Plone/Members/dgen/mymeetings/meeting-config-college/copy3_of_recurringofficialreport2', object_uid='1b8f6225afac4da79546860b86417371', this, msgName=null, view_name='@@delete_givenuid', redirect=null);" style="cursor:pointer" src="http://localhost:8081/Plone/delete_icon.png">
        <img title="Envoyer" onclick="javascript:confirmDeleteObject(base_url='http://localhost:8081/Plone/Members/dgen/mymeetings/meeting-config-college/copy3_of_recurringofficialreport2', object_uid='1b8f6225afac4da79546860b86417371', this, msgName=null, view_name='@@delete_givenuid', redirect=null);" style="cursor:pointer" src="/Plone/++resource++imio.esign/digital_signature_pen.png">
        <img title="Voir" onclick="javascript:confirmDeleteObject(base_url='http://localhost:8081/Plone/Members/dgen/mymeetings/meeting-config-college/copy3_of_recurringofficialreport2', object_uid='1b8f6225afac4da79546860b86417371', this, msgName=null, view_name='@@delete_givenuid', redirect=null);" style="cursor:pointer" src="/Plone/++resource++imio.esign/view_element.png">
        """


class SessionsTable(Table):
    cssClassEven = "even"
    cssClassOdd = "odd"
    cssClasses = {"table": "listing nosort sessions-table width-full"}
    sortOn = None
    results = []

    def __init__(self, context, view, request, items=None):
        super(SessionsTable, self).__init__(context, request)
        self.view = view
        self._items = items

    @property
    def values(self):
        return self._items

    def setUpColumns(self):
        ctx, req, tbl = self.context, self.request, self
        return [
            IdColumn(ctx, req, tbl),
            StateColumn(ctx, req, tbl),
            TitleColumn(ctx, req, tbl),
            LastUpdateColumn(ctx, req, tbl),
            SignersColumn(ctx, req, tbl),
            FilesColumn(ctx, req, tbl),
            ActionsColumn(ctx, req, tbl),
        ]
