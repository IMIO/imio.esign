# -*- coding: utf-8 -*-

from AccessControl import Unauthorized
from copy import deepcopy
from datetime import datetime
from datetime import timedelta
from imio.esign import _
from imio.esign import manage_session_perm
from imio.esign.audit import audit
from imio.esign.browser.table import external_session_link
from imio.esign.browser.table import SessionsTable
from imio.esign.config import get_esign_registry_enabled
from imio.esign.config import get_esign_registry_parapheo_url
from imio.esign.config import get_esign_registry_signing_users_email_content
from imio.esign.utils import create_external_session
from imio.esign.utils import get_session_annotation
from imio.esign.utils import get_session_info
from imio.esign.utils import get_sessions_for
from imio.esign.utils import get_state_description
from imio.esign.utils import remove_session
from imio.helpers.content import uuidToObject
from imio.helpers.emailer import create_html_email
from imio.helpers.emailer import send_email
from imio.helpers.security import separate_fullname
from imio.prettylink.interfaces import IPrettyLink
from imio.pyutils.utils import safe_encode
from imio.pyutils.utils import shortuid_decode_id
from plone import api
from plone.app.layout.viewlets import ViewletBase
from Products.CMFCore.utils import getToolByName
from Products.CMFPlone.utils import base_hasattr
from Products.Five import BrowserView
from Products.PageTemplates.Expressions import SecureModuleImporter
from zope.browserpage.viewpagetemplatefile import ViewPageTemplateFile
from zope.cachedescriptors.property import CachedProperty
from zope.component import getMultiAdapter
from zope.i18n import translate
from zope.interface import implementer
from zope.pagetemplate.pagetemplate import PageTemplate
from zope.publisher.interfaces import IPublishTraverse

import csv
import json
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

    def __call__(self):
        if not self.available():
            raise Unauthorized
        return super(SessionsListingView, self).__call__()

    def available(self):
        return get_esign_registry_enabled()

    def render_table(self):
        table = SessionsTable(self.context, self, self.request, self.get_sessions())
        table.update()
        return table.render()

    def get_sessions(self):
        sessions = []
        annot_sessions = deepcopy(get_session_annotation()["sessions"])
        for session_id, session in sorted(annot_sessions.items(), key=lambda x: x[0],
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
        if not self.may_delete_session():
            raise Unauthorized
        session_id = self.request.get("esign_session_id")
        if not session_id:
            api.portal.show_message(_("No session ID provided!"), request=self.request, type="error")
            return self.request.RESPONSE.redirect(self.context.absolute_url())

        session_id = int(session_id)
        sessions = get_session_annotation()["sessions"]
        if session_id in sessions:
            remove_session(session_id)
            audit("delete_session", "session={}".format(session_id))
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
        if not self.may_create_external_sessions():
            raise Unauthorized
        if session_id is None:
            session_id = self.request.get("session_id", None)
        if session_id is None:
            api.portal.show_message(_("No session ID provided!"), request=self.request, type="error")
            return self.context.absolute_url() + "/@@parapheo"
        resp = create_external_session(int(session_id))
        if resp == "_session_not_found_":
            audit("send_to_external_service", "session={} error=session_not_found".format(session_id))
            api.portal.show_message(
                _("Session with ID ${id} doesn't exist anymore !", mapping={"id": session_id}),
                request=self.request,
                type="error",
            )
        elif resp == "_no_seal_code_":
            audit("send_to_external_service", "session={} error=no_seal_code".format(session_id))
            api.portal.show_message(
                _("No seal code defined in configuration ! Session ${id} not sent.", mapping={"id": session_id}),
                request=self.request,
                type="error",
            )
        elif resp == "_no_seal_email_":
            audit("send_to_external_service", "session={} error=no_seal_email".format(session_id))
            api.portal.show_message(
                _("No seal email defined in configuration ! Session ${id} not sent.", mapping={"id": session_id}),
                request=self.request,
                type="error",
            )
        elif resp == "_no_files_":
            audit("send_to_external_service", "session={} error=no_files".format(session_id))
            api.portal.show_message(
                _("No files found to be sent ! Session ${id} not sent.", mapping={"id": session_id}),
                request=self.request,
                type="error",
            )
        elif resp.status_code == 200:
            audit("send_to_external_service", "session={} status=200".format(session_id))
            api.portal.show_message(_("External session sent successfully!"), request=self.request, type="info")
        else:
            audit("send_to_external_service", "session={} status={} reason={}".format(
                session_id, resp.status_code, resp.reason))
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
            if self.sessions:
                return self.index()
            return self.sessions_listing_view(self.context, self.request).render_table()
        return ""

    @CachedProperty
    def sessions(self):
        session_id = self.request.form.get("esign_session_id[]", None)
        try:
            session_id = int(session_id)
        except (TypeError, ValueError):
            return {}
        session = {}
        session_info = get_session_info(session_id)
        if session_info:
            session = {session_id: session_info}
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

    def collapsible_css_default(self):
        """Default CSS class to apply on the collapsible."""
        return "collapsible active"

    def collapsible_content_css_default(self):
        """Default CSS class to apply on the collapsible."""
        return "collapsible-content"

    def get_state_description(self, state):
        return translate(get_state_description(state), context=self.request, domain="imio.esign")


class ItemSessionInfoViewlet(FacetedSessionInfoViewlet):
    """Show session info for all sessions linked to a context item."""

    def available(self):
        """Global availability of the viewlet."""
        return True

    def render(self):
        """Render the viewlet."""
        if self.sessions:
            return self.index()
        return ""

    @CachedProperty
    def sessions(self):
        """Return all sessions that contain files from this context."""
        return get_sessions_for(self.context.UID())


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
            title=page_title, heading=heading, message=message
        )

        return html


class SigningUsersCsv(BrowserView):
    """Get users, checking for duplicate emails, output a CSV, and send emails.
    This view can be subclassed to redefine custom filtering logic.
    """

    index = ViewPageTemplateFile("templates/signing_users.pt")

    def __call__(self):
        # Handle CSV download
        if self.request.get("action") == "download_csv":
            return self._download_csv()

        # Handle email sending
        if self.request.get("action") == "send_emails":
            return self._send_emails()

        # Default: display the table
        return self.index()

    def filter_user(self, user_data):
        """Filter method to determine if a user should be included by default.

        :param user_data: dict containing user data (userid, email, lastname, firstname, fullname)
        :return: True to include the user by default, False to exclude
        """
        hps = api.content.find(
            portal_type="held_position",
            userid=user_data["userid"],
        )
        for hp in hps:
            hp_obj = hp.getObject()
            if base_hasattr(hp_obj, "usages") and "signer" in hp_obj.usages:
                return True

        user_obj = api.user.get(userid=user_data["userid"])
        if user_obj:
            for group in api.group.get_groups(user=user_obj):
                if group.getId().endswith("watchers"):
                    return True

        return False

    def get_users_data(self):
        """Get all users data sorted by filter status then userid.

        :return: list of user data dictionaries with 'checked' status
        """
        fn_first = True
        portal = api.portal.get()
        catalog = getToolByName(portal, "portal_catalog")
        acl_users = getToolByName(portal, "acl_users")

        all_users_data = []
        email_registry = {}

        for user_info in acl_users.searchUsers():
            userid = user_info.get("userid")
            if not userid:
                continue

            # Skip duplicates
            if any(u["userid"] == userid for u in all_users_data):
                continue

            user_obj = api.user.get(userid=userid)
            if not user_obj:
                continue

            email = user_obj.getProperty("email", "")
            fullname = user_obj.getProperty("fullname", "")
            lastname = firstname = ""

            # Do we have a person with this userid?
            brains = catalog.searchResults(portal_type="person", userid=userid)
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

            # Determine if user should be checked by default
            user_data["checked"] = self.filter_user(user_data)

            all_users_data.append(user_data)

            if email:
                email_registry.setdefault(email, []).append(userid)

        # Calculate duplicates
        duplicates = {email: userids for email, userids in email_registry.items() if len(userids) > 1}

        # Mark users with duplicate emails
        for user_data in all_users_data:
            user_data["has_duplicate_email"] = user_data["email"] in duplicates

        # Sort: filtered users first (checked=True), then by userid
        all_users_data.sort(key=lambda x: (not x["checked"], x["userid"]))

        return all_users_data, duplicates

    def _get_selected_userids(self):
        """Get list of selected user IDs from request.

        Expects a JSON-formatted list in 'selected_users' parameter.
        Returns an empty list if the input is not valid JSON.
        """
        selected = self.request.get("selected_users", "")

        if not selected:
            return []

        # Parse JSON array
        try:
            return json.loads(selected)
        except (ValueError, TypeError):
            return []

    def _download_csv(self):
        """Generate and download CSV file with selected users."""
        selected_userids = self._get_selected_userids()

        if not selected_userids:
            api.portal.show_message(_("No users selected for CSV download."), request=self.request, type="warning")
            return self.request.RESPONSE.redirect(self.context.absolute_url() + "/@@signing-users-csv")

        all_users_data, __ = self.get_users_data()

        # Filter to only selected users
        selected_users = [u for u in all_users_data if u["userid"] in selected_userids]

        # Generate CSV
        csv_output = StringIO()
        writer = csv.DictWriter(
            csv_output,
            fieldnames=["userid", "email", "lastname", "firstname", "fullname"],
            delimiter=",",
            quoting=csv.QUOTE_MINIMAL,
        )
        writer.writeheader()
        for user_data in selected_users:
            writer.writerow(
                {
                    "userid": safe_encode(user_data["userid"]),
                    "email": safe_encode(user_data["email"]),
                    "lastname": safe_encode(user_data["lastname"]),
                    "firstname": safe_encode(user_data["firstname"]),
                    "fullname": safe_encode(user_data["fullname"]),
                }
            )

        output = csv_output.getvalue()
        response = self.request.RESPONSE
        response.setHeader("Content-Type", "text/csv; charset=utf-8")
        response.setHeader("Content-Disposition", "attachment; filename=signing_users_selected.csv")
        return output

    def _send_emails(self):
        """Send emails to selected users."""
        selected_userids = self._get_selected_userids()

        if not selected_userids:
            api.portal.show_message(_("No users selected for email sending."), request=self.request, type="warning")
            return self.request.RESPONSE.redirect(self.context.absolute_url() + "/@@signing-users-csv")

        email_content = get_esign_registry_signing_users_email_content()
        if not email_content:
            api.portal.show_message(
                _("Email content is not configured in the settings."), request=self.request, type="error"
            )
            return self.request.RESPONSE.redirect(self.context.absolute_url() + "/@@signing-users-csv")

        all_users_data, _duplicates = self.get_users_data()
        selected_users = [u for u in all_users_data if u["userid"] in selected_userids]

        portal_email = api.portal.get().getProperty("email_from_address")
        if not portal_email:
            api.portal.show_message(_("Portal from email is not configured."), request=self.request, type="error")
            return self.request.RESPONSE.redirect(self.context.absolute_url() + "/@@mail-controlpanel")

        success_count = 0
        failed_count = 0
        for user_data in selected_users:
            if not user_data["email"]:
                failed_count += 1
                api.portal.show_message(
                    _(
                        "User ${userid} has no email address configured. Skipping.",
                        mapping={"userid": user_data["userid"]},
                    ),
                    request=self.request,
                    type="warning",
                )
                continue

            personalized_content = self._render_email_content(email_content, user_data)
            # personalized_content = str(email_content).format(**user_data).replace("\n", "<br>\n")

            # Create and send email
            try:
                eml = create_html_email(personalized_content, with_plain=True)
                subject = translate(_(u"You have been invited to Paraphéo"), context=self.request)

                status, error = send_email(
                    eml, subject=subject, mfrom=portal_email, mto=user_data["email"], immediate=False
                )

                if status:
                    success_count += 1
                else:
                    raise Exception(error)
            except Exception as e:
                failed_count += 1
                error = str(e)
                api.portal.show_message(
                    _(
                        "Failed to send email to ${userid}.",
                        mapping={"userid": user_data["userid"]},
                    )
                    + " "
                    + error,
                    request=self.request,
                    type="error",
                )
                continue

        if success_count > 0:
            api.portal.show_message(
                _("Emails sent successfully to ${count} users.", mapping={"count": success_count}),
                request=self.request,
                type="info",
            )

        if failed_count > 0:
            api.portal.show_message(
                _("Failed to send emails to ${count} users.", mapping={"count": failed_count}),
                request=self.request,
                type="warning",
            )

        return self.request.RESPONSE.redirect(self.context.absolute_url() + "/@@signing-users-csv")

    def _render_email_content(self, template, user_data):
        """Render the email content template with user data.

        :param template: The email content template (TAL compliant)
        :param user_data: dict containing user data (userid, email, lastname, firstname, fullname)
        :return: Rendered email content as a string
        """
        pt = PageTemplate()
        pt.pt_source_file = lambda: "none"
        pt.write(template)
        namespace = pt.pt_getContext()
        namespace.update(
            {
                "request": self.request,
                "view": self,
                "context": self.context,
                "user_data": user_data,
                "parapheo_url": get_esign_registry_parapheo_url(),
                "modules": SecureModuleImporter,
            }
        )
        return pt.pt_render(namespace)


class EsignMacros(BrowserView):
    """ """
