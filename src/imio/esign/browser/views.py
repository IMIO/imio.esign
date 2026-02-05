# -*- coding: utf-8 -*-
from datetime import datetime
from datetime import timedelta
from imio.esign import _
from imio.esign import ESIGN_CREDENTIALS
from imio.esign import ESIGN_ROOT_URL
from imio.esign import manage_session_perm
from imio.esign.browser.table import external_session_link
from imio.esign.browser.table import SessionsTable
from imio.esign.config import get_registry_enabled
from imio.esign.utils import create_external_session
from imio.esign.utils import get_session_annotation
from imio.esign.utils import remove_session
from imio.helpers.content import uuidToObject
from imio.helpers.security import separate_fullname
from imio.prettylink.interfaces import IPrettyLink
from imio.pyutils.utils import safe_encode
from imio.pyutils.utils import shortuid_decode_id
from plone import api
from plone.app.layout.viewlets import ViewletBase
from Products.CMFCore.utils import getToolByName
from Products.Five import BrowserView
from zope.browserpage.viewpagetemplatefile import ViewPageTemplateFile
from zope.component import getMultiAdapter
from zope.i18n import translate
from zope.interface import implementer
from zope.publisher.interfaces import IPublishTraverse

import csv
import os


try:
    from StringIO import StringIO  # Python 2
except ImportError:
    from io import StringIO  # Python 3


class SessionsListingView(BrowserView):
    """View to list sessions."""

    def __init__(self, context, request):
        super(SessionsListingView, self).__init__(context, request)
        self.portal = api.portal.get()
        self.portal_url = self.portal.absolute_url()

    def available(self):
        return get_registry_enabled()

    def render_table(self):
        table = SessionsTable(self.context, self, self.request, self.get_sessions())
        table.update()
        return table.render()

    def get_sessions(self):
        sessions = []
        for session_id, session in sorted(get_session_annotation()["sessions"].items(), key=lambda x: x[0],
                                          reverse=True):
            session["id"] = session_id
            sessions.append(session)
        return sessions

    def get_dashboard_link(self, session):
        raise NotImplementedError

    def get_sessions_url(self):
        return self.portal_url


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

        return self.request.RESPONSE.redirect(self.context.absolute_url() + "/@@parapheo")

    def may_delete_session(self):
        """Check if the user may delete sessions"""
        return api.user.has_permission(manage_session_perm, obj=self.context)


class ExternalSessionCreateView(BrowserView):
    """View to create a session in Luxtrust."""

    def __call__(self, session_id=None):
        if session_id is None:
            session_id = self.request.get("session_id", None)
        if session_id is None:
            api.portal.show_message(_("No session ID provided!"), request=self.request, type="error")
            return self.context.absolute_url() + "/@@parapheo"
        resp = create_external_session(
            int(session_id),
            b64_cred=ESIGN_CREDENTIALS,
            esign_root_url=ESIGN_ROOT_URL,
        )
        if resp == "_session_not_found_":
            api.portal.show_message(
                _("Session with ID ${id} doesn't exist anymore !", mapping={"id": session_id}),
                request=self.request,
                type="error",
            )
        elif resp == "_no_seal_code_":
            api.portal.show_message(
                _("No seal code defined in configuration ! Session ${id} not sent.", mapping={"id": session_id}),
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
        return self.context.absolute_url() + "/@@parapheo"

    def may_create_external_sessions(self):
        """Check if the user may create external sessions"""
        return api.user.has_permission(manage_session_perm, obj=self.context)


class FacetedSessionInfoViewlet(ViewletBase):
    """Show selected session info inside faceted results."""

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

    def get_table_rows(self, column):
        """Get the table rows following the column"""
        return {1: ["session_id", "state", "update_date", "sealed"],
                2: ["external_link", "signers"]}.get(column, [])

    def ext_session_link(self, session):
        return external_session_link(session)

    @property
    def session_listing_url(self):
        return api.portal.get().absolute_url() + "/@@parapheo"

    def can_display_sessions_listing_link(self):
        return getMultiAdapter((api.portal.get(), self.request), name="parapheo").available()


class ItemSessionInfoViewlet(FacetedSessionInfoViewlet):
    """Show selected session info for an item."""

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


@implementer(IPublishTraverse)
class DownloadFileView(BrowserView):
    """View to download a file based on an identifier passed in the URL path.

    Finally not used !"""

    shortuid_separator = "-"
    named_blob_file_attribute = "file"
    download_time_delta = timedelta(days=120)

    def __init__(self, context, request):
        super(DownloadFileView, self).__init__(context, request)
        self.file_id = None

    def publishTraverse(self, request, name):
        """Capture the file identifier from the URL path.

        This method is called by Zope's traversal mechanism when accessing
        /download-file/1234-567. It captures '1234-567'.
        """
        if self.file_id is None:
            self.file_id = name
        else:
            pass
        return self

    def __call__(self):
        """Handle the file download request and return a html response."""
        if self.file_id is None:
            message = translate(_("A file identifier must be passed in the url !"), context=self.request)
            return self.html_message(message)
        decoded_uid = shortuid_decode_id(self.file_id, self.shortuid_separator)
        if decoded_uid is None:
            message = translate(_("This file identifier is not correct !"), context=self.request)
            return self.html_message(message)
        file_obj = uuidToObject(decoded_uid, unrestricted=True)
        if file_obj is None:
            message = translate(_("The corresponding file identifier cannot be retrieved (${uid}) !",
                                  mapping={"uid": safe_encode(self.file_id)}),
                                context=self.request)
            return self.html_message(message)
        # Verify date - check if file is not too old
        if self.download_time_delta is not None:
            modification_date = file_obj.modified()
            if hasattr(modification_date, 'asdatetime'):
                modification_date = modification_date.asdatetime()
            modification_date = modification_date.date()
            if datetime.now().date() - modification_date > self.download_time_delta:
                message = translate(
                    _("The download period for this file has expired (was ${valid_date}) !",
                      mapping={"valid_date": datetime.strftime(modification_date + self.download_time_delta,
                                                               "%Y-%m-%d")}),
                    context=self.request)
                return self.html_message(message)
        # Get file content
        nbf = getattr(file_obj, self.named_blob_file_attribute, None)
        if nbf is None:
            message = translate(_("The corresponding file content cannot be retrieved (${uid}) !",
                                  mapping={"uid": safe_encode(decoded_uid)}),
                                context=self.request)
            return self.html_message(message)
        # Serve the file
        response = self.request.RESPONSE
        filename = safe_encode(nbf.filename)
        if "__" in filename:
            filename = filename.split("__")[0] + os.path.splitext(filename)[1]
        response.setHeader("Content-Type", nbf.contentType)
        response.setHeader("Content-Disposition", 'inline; filename="{}"'.format(filename))
        response.setHeader("Content-Length", str(len(nbf.data)))
        return nbf.data

    def html_message(self, message):
        """Returns a html message

        :param message: translated message to display
        :return: File content or HTML response
        """
        response = self.request.RESPONSE
        response.setHeader('Content-Type', 'text/html; charset=utf-8')

        # Translate HTML content
        page_title = translate(_("Signed file download"), context=self.request)
        heading = translate(_("Signed file download"), context=self.request)

        html = u"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset='utf-8'>
            <title>{title}</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 40px; }}
                .info-box {{
                    background-color: #fff3cd;
                    border: 2px solid #ff9800;
                    padding: 20px;
                    border-radius: 5px;
                }}
                h1 {{ color: #e65100; }}
                p {{ color: #663c00; }}
            </style>
        </head>
        <body>
            <div class='info-box'>
                <h1>⚠️ {heading}</h1>
                <p>{message}</p>
            </div>
        </body>
        </html>
        """.format(
            title=page_title,
            heading=heading,
            message=message
        )

        return html


class SigningUsersCsv(BrowserView):
    """Get users, checking for duplicate emails, and output a CSV.
    This view can be subclassed to redefine custom filtering logic.
    """

    def __call__(self):
        fn_first = True
        if self.request.get("fn_first", "1") == "0":
            fn_first = False
        apply_filter = self.request.get("apply_filter", "1") == "1"
        if self.request.get("download", "") == "1":
            return self._generate_csv(fn_first, apply_filter)
        return self._generate_html(fn_first, apply_filter=apply_filter)

    def filter_user(self, user_data):
        """Filter method to determine if a user should be included in CSV output.

        :param user_data: dict containing user data (userid, email, lastname, firstname, fullname)
        :return: True to include the user in CSV, False to exclude
        """
        return True

    def _collect_users_data(self, fn_first):
        """Get users and duplicates.

        :param fn_first: Boolean indicating if firstname comes first
        :return: (all_users_data, filtered_users_data, duplicates)
        """
        portal = api.portal.get()
        catalog = getToolByName(portal, "portal_catalog")
        acl_users = getToolByName(portal, "acl_users")

        all_users_data = {}
        email_registry = {}

        for user_info in acl_users.searchUsers():
            userid = user_info.get("userid")
            if not userid or userid in all_users_data:
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

            user_data = {
                "userid": userid,
                "email": email,
                "lastname": lastname,
                "firstname": firstname,
                "fullname": fullname,
            }
            all_users_data[userid] = user_data

            if email:
                email_registry.setdefault(email, []).append(userid)

        duplicates = {email: userids for email, userids in email_registry.items() if len(userids) > 1}

        # Apply custom filter
        filtered_users_data = {}

        for userid, user_data in all_users_data.items():
            if self.filter_user(user_data):
                filtered_users_data[userid] = user_data

        return all_users_data, filtered_users_data, duplicates

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

    def _generate_csv(self, fn_first, apply_filter=True):
        """Generate csv file

        :param fn_first: Boolean indicating if firstname comes first
        :param apply_filter: Boolean to apply or not the filter_user method
        """
        all_users_data, filtered_users_data, duplicates = self._collect_users_data(fn_first)
        users_data = filtered_users_data if apply_filter else all_users_data
        output = self._create_csv(users_data)
        response = self.request.RESPONSE
        response.setHeader("Content-Type", "text/csv; charset=utf-8")
        filename = "plone_users_list_filtered.csv" if apply_filter else "plone_users_list_all.csv"
        response.setHeader("Content-Disposition", "attachment; filename={}".format(filename))
        return output

    def _generate_html(self, fn_first, apply_filter=True):
        """Generate html output with duplicates."""
        # Get all users and filtered users in one call
        all_users_data, filtered_users_data, duplicates = self._collect_users_data(fn_first)
        users_data = filtered_users_data if apply_filter else all_users_data
        csv_text = self._create_csv(users_data)

        base_url = self.context.absolute_url() + "/@@signing-users-csv"

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
            "text-decoration: none; border-radius: 5px; margin: 0 0 10px; }",
            ".download-btn:hover { background-color: #0056b3; }",
            ".download-btn.secondary { background-color: #6c757d; }",
            ".download-btn.secondary:hover { background-color: #5a6268; }",
            ".stats { margin: 20px 0; }",
            "</style>",
            "</head><body>",
            "<h1>Plone list users</h1>",
            "<div class='stats'>",
            "<p><strong>Total users (all) :</strong> {}</p>".format(len(all_users_data)),
            "<p><strong>Total users (filtered) :</strong> {}</p>".format(len(filtered_users_data)),
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
        html.append("<a href='{}?download=1&apply_filter=1' class='download-btn'>📥 Download CSV "
                    "(filtered)</a>".format(base_url))
        html.append("<a href='{}?download=1&apply_filter=0' class='download-btn secondary'>📥 Download CSV "
                    "(all users)</a>".format(base_url))
        html.append("<h2>Overview of CSV file{}</h2>".format(" (filtered)" if apply_filter else ""))
        html.append("<div class='csv-content'>{}</div>".format(csv_text.replace("<", "&lt;").replace(">", "&gt;")))
        html.append("</body></html>")

        response = self.request.RESPONSE
        response.setHeader("Content-Type", "text/html; charset=utf-8")

        return "\n".join(html)


class EsignMacros(BrowserView):
    """ """
