# -*- coding: utf-8 -*-
from imio.esign import _
from imio.esign import ESIGN_CREDENTIALS
from imio.esign import ESIGN_ROOT_URL
from imio.esign.browser.table import external_session_link
from imio.esign.browser.table import SessionsTable
from imio.esign.utils import create_external_session
from imio.esign.utils import get_session_annotation
from imio.esign.utils import remove_session
from imio.helpers.content import uuidToObject
from imio.helpers.security import separate_fullname
from imio.prettylink.interfaces import IPrettyLink
from imio.pyutils.utils import safe_encode
from plone import api
from plone.app.layout.viewlets import ViewletBase
from Products.CMFCore.utils import getToolByName
from Products.Five import BrowserView
from zope.browserpage.viewpagetemplatefile import ViewPageTemplateFile

import csv


try:
    from StringIO import StringIO  # Python 2
except ImportError:
    from io import StringIO  # Python 3


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
        sessions = []
        for session_id, session in get_session_annotation()["sessions"].items():
            session["id"] = session_id
            sessions.append(session)
        return sessions

    def get_dashboard_link(self, session):
        raise NotImplementedError


class SessionFilesView(BrowserView):
    """View to display documents of a session."""

    index = ViewPageTemplateFile("templates/session_files.pt")

    def __init__(self, context, request):
        super(SessionFilesView, self).__init__(context, request)
        self.files = []

    def __call__(self):
        session_id = int(self.request.get("session_id"))
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
        return get_session_annotation()["sessions"][session_id]

    def get_file_link(self, ctx, obj):
        return IPrettyLink(ctx).getLink() + " / " + IPrettyLink(obj).getLink()


class SessionDeleteView(BrowserView):
    """View to delete a session."""

    def __call__(self):
        session_id = self.request.get("esign_session_id")
        if not session_id:
            api.portal.show_message(_("No session ID provided!"), request=self.request, type="error")
            return self.request.RESPONSE.redirect(self.context.absolute_url())

        session_id = int(session_id)
        sessions = get_session_annotation()["sessions"]
        if session_id in sessions:
            remove_session(session_id)
            api.portal.show_message(_("Session deleted successfully!"), request=self.request, type="info")
        else:
            api.portal.show_message(_("Session not found!"), request=self.request, type="error")

        return self.request.RESPONSE.redirect(self.context.absolute_url() + "/@@esign-sessions-listing")


class ExternalSessionCreateView(BrowserView):
    """View to create a session in Luxtrust."""

    def __call__(self, session_id=None):
        if session_id is None:
            session_id = self.request.get("session_id", None)
        if session_id is None:
            api.portal.show_message(_("No session ID provided!"), request=self.request, type="error")
            return self.context.absolute_url() + "/@@esign-sessions-listing"
        resp = create_external_session(
            int(session_id),
            b64_cred=ESIGN_CREDENTIALS,
            esign_root_url=ESIGN_ROOT_URL,
        )
        if resp is None:
            api.portal.show_message(
                _("Session with ID ${id} doesn't exist anymore !", mapping={"id": session_id}),
                request=self.request,
                type="error",
            )
        elif resp.status_code == 200:
            api.portal.show_message(_("External session sent successfully!"), request=self.request, type="info")
        else:
            api.portal.show_message(
                _("Error while sending session: ${error}", mapping={"error": "{} {} {}".format(
                    resp.status_code, resp.reason, resp.text)}),
                request=self.request,
                type="error",
            )
        return self.context.absolute_url() + "/@@esign-sessions-listing"


class FacetedSessionInfoViewlet(ViewletBase):
    """Show selected session info inside faceted results."""

    index = ViewPageTemplateFile("templates/faceted_session_info.pt")
    sessions_listing_view = SessionsListingView  # to be overridden in subclass

    def available(self):
        """Global availability of the viewlet."""
        if self.sessions_collection_uid is None:
            return False
        return True

    @property
    def sessions_collection_uid(self):
        raise NotImplementedError("You must set sessions_collection_uid in subclass.")

    def render(self):
        """Render the viewlet."""
        if self.request.form.get("c1[]", None) == self.sessions_collection_uid:
            if self.session:
                return self.index()
            return self.sessions_listing_view(self.context, self.request).render_table()
        return ""

    @property
    def session(self):
        session = None
        session_id = self.request.form.get("esign_session_id[]", None)
        if not session_id:
            return
        sessions = get_session_annotation()["sessions"]
        session = sessions.get(int(session_id))
        if not session:
            return
        session["id"] = session_id
        return session

    def ext_session_link(self, session):
        return external_session_link(session)


class ItemSessionInfoViewlet(ViewletBase):
    """Show selected session info for an item."""

    index = ViewPageTemplateFile("templates/faceted_session_info.pt")

    def available(self):
        """Global availability of the viewlet."""
        return True

    def render(self):
        """Render the viewlet."""
        if self.session:
            return self.index()
        return ""

    @property
    def session(self):
        annot = get_session_annotation()
        for f_uid in annot["c_uids"].get(self.context.UID(), []):
            if f_uid in annot["uids"]:
                session = annot["sessions"].get(annot["uids"][f_uid], {})
                session["id"] = annot["uids"][f_uid]
                return session
        return {}

    def ext_session_link(self, session):
        return external_session_link(session)
# TODO clean up css


class AllUsersCsv(BrowserView):
    """Get all users, checking for duplicate emails, and output a CSV."""

    def __call__(self):
        fn_first = True
        if self.request.get("fn_first", "1") == "0":
            fn_first = False
        if self.request.get("download", "") == "1":
            return self._generate_csv(fn_first)
        return self._generate_html(fn_first)

    def _collect_users_data(self, fn_first):
        """Get users and duplicates."""
        portal = api.portal.get()
        catalog = getToolByName(portal, "portal_catalog")
        acl_users = getToolByName(portal, "acl_users")

        users_data = {}
        email_registry = {}

        for user_info in acl_users.searchUsers():
            userid = user_info.get("userid")
            if not userid or userid in users_data:
                continue
            user_obj = api.user.get(userid=userid)
            if not user_obj:
                continue

            email = user_obj.getProperty("email", "")
            fullname = user_obj.getProperty("fullname", "")
            lastname = firstname = ""

            # Do we have a person with this userid ?
            brains = catalog.searchResults(
                portal_type="person",
                userid=userid
            )
            if brains:
                person = brains[0].getObject()
                lastname = getattr(person, "lastname", "") or ""
                firstname = getattr(person, "firstname", "") or ""

            if not lastname and not firstname:
                start = api.portal.get_registry_record(
                    "imio.dms.mail.browser.settings.IImioDmsMailConfig.omail_fullname_used_form", default=None
                )
                if start is not None:
                    fn_first = start == "firstname"
                firstname, lastname = separate_fullname(user_obj, fn_first=fn_first)

            users_data[userid] = {
                "userid": userid,
                "email": email,
                "lastname": lastname,
                "firstname": firstname,
                "fullname": fullname,
            }

            if email:
                email_registry.setdefault(email, []).append(userid)

        duplicates = {email: userids for email, userids in email_registry.items() if len(userids) > 1}

        return users_data, duplicates

    def _create_csv(self, users_data):
        csv_output = StringIO()
        writer = csv.DictWriter(
            csv_output,
            fieldnames=["userid", "email", "lastname", "firstname", "fullname"],
            delimiter=",",
            quoting=csv.QUOTE_MINIMAL
        )
        writer.writeheader()
        for userid in users_data:
            user_data = users_data[userid]
            writer.writerow({
                "userid": safe_encode(userid),
                "email": safe_encode(user_data["email"]),
                "lastname": safe_encode(user_data["lastname"]),
                "firstname": safe_encode(user_data["firstname"]),
                "fullname": safe_encode(user_data["fullname"]),
            })
        return csv_output.getvalue()

    def _generate_csv(self, fn_first):
        """Generate csv file"""
        users_data, duplicates = self._collect_users_data(fn_first)
        output = self._create_csv(users_data)
        response = self.request.RESPONSE
        response.setHeader("Content-Type", "text/csv; charset=utf-8")
        response.setHeader("Content-Disposition", "attachment; filename=plone_users_list.csv")
        return output

    def _generate_html(self, fn_first):
        """Generate html output with duplicates."""
        users_data, duplicates = self._collect_users_data(fn_first)
        csv_text = self._create_csv(users_data)

        html = [
            "<!DOCTYPE html>",
            "<html><head>",
            "<meta charset='utf-8'>",
            "<title>Liste des utilisateurs Plone</title>",
            "<style>",
            "body { font-family: Arial, sans-serif; margin: 20px; }",
            "h1 { color: #333; }",
            "h2 { color: #666; margin-top: 10px; }",
            ".error-section { background-color: #fff3cd; border: 1px solid #ffc107; padding: 5px; margin: 20px 0; "
            "border-radius: 5px; }",
            ".success-section { background-color: #d4edda; border: 1px solid #28a745; padding: 5px; margin: 20px 0; "
            "border-radius: 5px; }",
            ".duplicate { margin: 10px 0; padding: 10px; background-color: #f8d7da; border-left: 4px solid #dc3545; }",
            ".duplicate strong { color: #721c24; }",
            ".csv-content { background-color: #f5f5f5; border: 1px solid #ddd; padding: 15px; margin: 20px 0; "
            "font-family: monospace; white-space: pre-wrap; overflow-x: auto; max-height: 400px; overflow-y: auto; }",
            ".download-btn { display: inline-block; padding: 10px 20px; background-color: #007bff; color: white; "
            "text-decoration: none; border-radius: 5px; margin: 10px 0; }",
            ".download-btn:hover { background-color: #0056b3; }",
            ".stats { margin: 20px 0; }",
            "</style>",
            "</head><body>",
            "<h1>Plone list users</h1>",
            "<div class='stats'>",
            "<p><strong>Total users :</strong> {}</p>".format(len(users_data)),
            "<p><strong>Total duplicated emails :</strong> {}</p>".format(len(duplicates)),
            "</div>",
        ]
        if duplicates:
            html.append("<div class='error-section'>")
            html.append("<h2>⚠️ email duplicate</h2>")
            for email, userids in sorted(duplicates.items()):
                html.append("<div class='duplicate'>")
                html.append("<strong>Email :</strong> {}<br>".format(safe_encode(email)))
                html.append("<strong>Users :</strong> {}".format(", ".join([safe_encode(uid) for uid in userids])))
                html.append("</div>")
            html.append("</div>")
        else:
            html.append("<div class='success-section'>")
            html.append("<h2>✓ No email duplicate</h2>")
            html.append("</div>")

        html.append("<h2>Download CSV file</h2>")
        html.append("<a href='{}?download=1' class='download-btn'>📥 Download CSV file</a>".format(
            self.context.absolute_url() + "/@@all-users-csv"
        ))

        html.append("<h2>Overview of CSV file</h2>")
        html.append("<div class='csv-content'>{}</div>".format(csv_text.replace("<", "&lt;").replace(">", "&gt;")))
        html.append("</body></html>")

        response = self.request.RESPONSE
        response.setHeader("Content-Type", "text/html; charset=utf-8")

        return "\n".join(html)
