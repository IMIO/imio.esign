# -*- coding: utf-8 -*-

from eea.facetednavigation.interfaces import IFacetedNavigable
from imio.esign import _
from plone import api
from Products.CMFPlone.utils import safe_unicode
from z3c.table.column import Column
from z3c.table.table import Table
from zope.component import getMultiAdapter
from zope.i18n import translate


class IdColumn(Column):
    header = _("ID")
    weight = 10
    cssClasses = {"th": "th_header_sessions_id"}

    def renderHeadCell(self):
        """
        Override to add JS that will the "No results" link when displayed in faceted dashboard.
        """
        res = super(IdColumn, self).renderHeadCell()
        if IFacetedNavigable.providedBy(self.context):
            res += "<script>$('div.table_faceted_results').hide();</script>"
        return res

    def renderCell(self, item):
        # this will hide the "No results" link when displayed in faceted dashboard
        return "<span id='{0}'>{0}</span>".format(str(item.get("id")))


def external_session_link(session, title=None):
    """Return a tag with the sign external session."""
    title = title or session.get("title", "") or session.get("sign_id", "")
    if not session["sign_id"] or not session["sign_url"]:
        return u"<span>{0}</span>".format(title)
    return u'<a href="{url}" target="_blank">{title}</a>'.format(
        url=session["sign_url"],
        title=safe_unicode(title),
    )


class StateColumn(Column):
    header = _("State")
    weight = 20
    cssClasses = {"th": "th_header_sessions_state"}

    def renderCell(self, item):
        return translate(
            (item.get("state", "")), context=self.request, default=item.get("state", ""), domain="imio.esign"
        )


class TitleColumn(Column):
    header = _("Title")
    weight = 30
    cssClasses = {"th": "th_header_sessions_title"}

    def renderCell(self, item):
        title = safe_unicode(item.get("title", ""))
        if item["sign_url"]:
            return external_session_link(item, title=title)
        else:
            return title


class LastUpdateColumn(Column):
    header = _("Last update")
    weight = 40
    cssClasses = {"th": "th_header_sessions_last_update"}

    def renderCell(self, item):
        last_update = item.get("last_update")
        return self.context.unrestrictedTraverse('@@plone').toLocalizedTime(
            last_update, long_format=True)


class SignersColumn(Column):
    header = _("Signers")
    weight = 50
    cssClasses = {"th": "th_header_sessions_signers"}

    def renderCell(self, item):
        signers = item.get("signers") or []
        parts = [
            "<li>%s, %s%s (%s)</li>" % (
                s.get("fullname", ""),
                s.get("position"),
                " (%s)" % s.get("status") if s.get("status") else "",
                s.get("email"), )
            for s in signers
        ]
        return safe_unicode("<ol>%s</ol>" % "".join(parts))


class FilesColumn(Column):
    header = _("Files")
    weight = 60
    cssClasses = {"th": "th_header_sessions_documents",
                  "td": "documents-column"}

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
                base_url = api.portal.get().absolute_url()

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

        return html


class ActionsColumn(Column):
    """ """

    header = _("Actions")
    weight = 70
    cssClasses = {"th": "th_header_sessions_actions",
                  "td": "actions-column"}

    def renderCell(self, item):
        session_id = item.get("id")
        dashboard_link = self.table.view.get_dashboard_link({"id": session_id})
        sessions_url = self.table.view.get_sessions_url()
        portal = api.portal.get()
        # if not sessions_url.endswith("/"):
        #    sessions_url += "/"
        admin_buttons = u""
        if getMultiAdapter((portal, self.request), name="esign-session-delete").may_delete_session():
            admin_buttons = u"""
            <img width="16" height="16" title="{delete}" style="cursor:pointer" src="delete_icon.png"
            onclick="javascript:confirmDeleteObject(base_url='{sessions_url}', object_uid=null, this,
            msgName=null, view_name='@@esign-session-delete?esign_session_id={session_id}', redirect=null);">
            """.format(
                delete=translate(_("Delete session"), context=self.request),
                sessions_url=sessions_url,
                session_id=session_id,
            )
        if (item.get("state") == "draft"
                and getMultiAdapter((portal, self.request),
                                    name="external-esign-session-create").may_create_external_sessions()):
            admin_buttons += u"""
            <img width="16" height="16" title="{send}" style="cursor:pointer" src="++resource++imio.esign/parapheo.svg"
            onclick="javascript:callViewAndReload('{sessions_url}','@@external-esign-session-create',
            {{'session_id': '{session_id}'}});">
            """.format(
                sessions_url=sessions_url,
                session_id=session_id,
                send=translate(_("Create external session"), context=self.request),
            )
        dashboard_button = u"""
        <a href="{dashboard_link}"><img title="{dashboard_view}" style="cursor:pointer"
        src="++resource++imio.esign/view_element.png"></a>
        """.format(  # noqa E501
            dashboard_link=dashboard_link,
            dashboard_view=translate(_("View session in dashboard"), context=self.request),
        )
        return admin_buttons + dashboard_button


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
