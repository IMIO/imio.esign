from imio.esign import _
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
        parts = ["<li>%s (%s)</li>" % (s.get("name", ""), s.get("status", "")) for s in signers]
        return "<ol>%s</ol>" % "".join(parts)


class DocumentsColumn(Column):
    header = _("Documents")
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

        # TODO: Refactor this
        html = (
            '<div id="session-docs" class="collapsible" '
            "onclick=\"toggleDetails('collapsible-session-docs_{0}', "
            "toggle_parent_active=true, parent_tag=null, "
            "load_view='@@esign-session-documents?session_id={0}', "
            "base_url='{1}');\"> {2}</div>"
            '<div id="collapsible-session-docs_{0}" class="collapsible-content" style="display: none;">'
            '<div class="collapsible-inner-content">'
            '<img src="{1}/spinner_small.gif" />'
            "</div></div>"
            """<a target="_parent" href="@@esign-session?session_id={0}" style="margin-top: 6px;">
                    <img class="categorized_elements_more_infos_icon" src="http://localhost:8081/Plone/++resource++collective.iconifiedcategory.images/more_infos.png">
                    <span>Tableau de bord</span>
                  </a>"""
        ).format(session_id, base_url, details_msg)

        return html


class ActionsColumn(Column):
    """ """

    header = _("Actions")
    weight = 70
    params = {
        "useIcons": True,
        "showHistory": False,
        "showActions": True,
        "showOwnDelete": False,
        "showArrows": True,
        "showTransitions": False,
        "showExtEdit": True,
        "edit_action_class": "dg_edit_action",
        "edit_action_target": "_blank",
    }
    cssClasses = {"td": "actions-column"}

    def renderCell(self, item):
        return ""


class SessionsTable(Table):
    cssClassEven = "even"
    cssClassOdd = "odd"
    cssClasses = {"table": "listing nosort sessions-table width-full"}
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
