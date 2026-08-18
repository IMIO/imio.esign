# -*- coding: utf-8 -*-

from eea.facetednavigation.interfaces import IFacetedNavigable
from html import escape
from imio.esign import _
from imio.esign.config import get_esign_registry_max_session_files
from imio.esign.config import get_esign_registry_max_session_size
from imio.esign.config import get_esign_registry_seal_code
from imio.esign.config import get_esign_registry_seal_email
from imio.esign.utils import get_state_description
from imio.helpers.security import check_zope_admin
from imio.pyutils.utils import safe_encode
from plone import api
from Products.CMFPlone.utils import safe_unicode
from z3c.table.column import Column
from z3c.table.table import Table
from zope.component import getMultiAdapter
from zope.i18n import translate

import html


class IdColumn(Column):
    # not translated so it stays short
    header = "Id"
    weight = 10
    cssClasses = {"th": "th_header_sessions_id",
                  "td": "id-column"}

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
    cssClasses = {"th": "th_header_sessions_state",
                  "td": "state-column"}

    def renderCell(self, item):
        state = escape(translate(
            (item.get("state", "")), context=self.request, default=item.get("state", ""), domain="imio.esign",
        ))
        title = escape(translate(get_state_description(item.get("state", "")), context=self.request,
                                 domain="imio.esign"))
        return (u"<span class='state-title state-title-{state_title_value}' title='{title}'>{state} "
                u"<span class='far fa-question-circle' />"
                u"</span>".format(state=state, title=title, state_title_value=item.get("state")))


class TitleColumn(Column):
    header = _("Title")
    weight = 30
    cssClasses = {"th": "th_header_sessions_title",
                  "td": "title-column"}

    def renderCell(self, item):
        title = safe_unicode(item.get("title", ""))
        if item["sign_url"]:
            return external_session_link(item, title=title)
        else:
            return title


class SealColumn(Column):
    header = _("Sealed")
    weight = 40
    cssClasses = {"th": "th_header_sessions_seal nosort",
                  "td": "seal-column"}

    def renderCell(self, item):
        if not item.get("seal"):
            return u""
        label = escape(translate(_("Sealed"), context=self.request))
        # icon: https://www.flaticon.com/free-icon/verification_3556787
        return (u"<img width='16' height='16' src='++resource++imio.esign/seal.png' title='{label}' "
                u"aria-label='{label}'></img>".format(label=label))


class SignersColumn(Column):
    header = _("Signers")
    weight = 50
    cssClasses = {"th": "th_header_sessions_signers",
                  "td": "signers-column"}

    def renderCell(self, item):
        signers = item.get("signers") or []
        parts = []
        for s in signers:
            icon_name = 'edit'
            css_class = "signer-not-signed"
            msgid = "status_title_not_signed"
            if s.get("status") == "signed":
                css_class = "signer-signed"
                msgid = "status_title_signed"
            elif s.get("status") == "refused":
                icon_name = 'ban'
                css_class = "signer-refused"
                msgid = "status_title_refused"
            parts.append(
                "<li>%s, %s (%s) %s</li>" % (
                    safe_encode(s.get("fullname", "")),
                    safe_encode(s.get("position")),
                    s.get("email"),
                    "<span class='fa fa-%s help %s' title='%s'></span>" % (
                        icon_name,
                        css_class,
                        safe_encode(html.escape(
                            translate(
                                msgid,
                                domain="imio.esign",
                                context=self.request)))),
                ))
        return safe_unicode("<ol>%s</ol>" % "".join(parts))


class FilesColumn(Column):
    SESSION_SIZE_WARNING_THRESHOLD = 0.8  # Warn when size reaches 80% of max
    header = _("Files")
    weight = 60
    cssClasses = {"th": "th_header_sessions_documents nosort",
                  "td": "documents-column"}

    def renderQuickLook(self, item):
        """Renders collapsible label with file count and session size info"""
        count = len(item.get("files", []))
        max_size_mb = get_esign_registry_max_session_size()
        max_size_bytes = max_size_mb * 1024 * 1024
        size_bytes = item.get("size", 0)
        size_mb = -(-size_bytes // (1024.0 * 1024.0))  # round size up to int
        size_style = (
            u' style="color:red"' if size_bytes >= self.SESSION_SIZE_WARNING_THRESHOLD * max_size_bytes else u""
        )
        # size_label = u"%d/%d MB" % (size_mb, max_size_mb)
        size_label = u"%d MB" % size_mb
        help_title = translate(
            _(
                "Session can contain max ${max_session_files} elements and have a max size of ${max_session_size} MB.",
                mapping={
                    "max_session_files": get_esign_registry_max_session_files(),
                    "max_session_size": get_esign_registry_max_session_size()
                },
            ),
            context=self.request,
            domain="imio.esign",
        )
        label = translate(
            _(
                "Quick look (${count} element(s), total size: ${size}) <span title='${help_title}' "
                "class='far fa-question-circle' />",
                mapping={
                    "count": count,
                    "size": u"<span%s>%s</span>" % (size_style, size_label),
                    "help_title": help_title,
                },
            ),
            context=self.request,
            domain="imio.esign",
        )
        return label

    def renderCell(self, item):
        """Render a collapsible block that loads the list on demand."""
        # Row identifier (unique per session)
        session_id = item.get("id")
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
            u"load_view='@@esign-session-files?session_id:int={0}', "
            u"base_url='{1}');\"> {2}</div>"
            u'<div id="collapsible-session-files_{0}" class="collapsible-content" style="display: none;">'
            u'<div class="collapsible-inner-content">'
            u'<img src="{1}/spinner_small.gif" />'
            u"</div></div>"
        ).format(session_id, base_url, self.renderQuickLook(item))

        return html


class LastUpdateColumn(Column):
    header = _("Last update")
    weight = 70
    cssClasses = {"th": "th_header_sessions_last_update",
                  "td": "last-update-column"}

    def renderCell(self, item):
        last_update = item.get("last_update")
        # make sortable
        value = "<span style='display:none'>{0}</span>".format(last_update)
        return value + self.context.unrestrictedTraverse('@@plone').toLocalizedTime(
            last_update, long_format=True)


class ActionsColumn(Column):
    """ """

    header = _("Actions")
    weight = 80
    cssClasses = {"th": "th_header_sessions_actions nosort",
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
        if (item.get("state") in ("draft", "draft_full")
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
        if getMultiAdapter((portal, self.request),
                           name="esign-session-recreate-form").may_recreate_session(item.get("state")):
            recreate_title = translate(_("Recreate session"), context=self.request)
            admin_buttons += u"""
            <a class="link-overlay-info" title="{recreate_title}" target="_blank"
               href="{sessions_url}/@@esign-session-recreate-form?esign_session_id={session_id}">
                <i class="fa fa-redo" style="cursor:pointer"></i>
            </a>
            """.format(
                recreate_title=recreate_title,
                sessions_url=sessions_url,
                session_id=session_id,
            )
        if check_zope_admin():
            admin_buttons += u"""
            <a class="link-overlay-info" href="{sessions_url}/@@session-annotation-info?session_id={session_id}"
            target="_blank">
                <span class="fa fa-info-circle" title="Annotation info"></span>
            </a>
            """.format(
                sessions_url=sessions_url,
                session_id=session_id,
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
    cssClasses = {"table": "listing sessions-table width-full"}
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
        columns = [
            IdColumn(ctx, req, tbl),
            StateColumn(ctx, req, tbl),
            TitleColumn(ctx, req, tbl),
            SignersColumn(ctx, req, tbl),
            FilesColumn(ctx, req, tbl),
            LastUpdateColumn(ctx, req, tbl),
            ActionsColumn(ctx, req, tbl),
        ]
        if get_esign_registry_seal_code() and get_esign_registry_seal_email():
            seal_col = SealColumn(ctx, req, tbl)
            columns.insert(4, seal_col)
        return columns
