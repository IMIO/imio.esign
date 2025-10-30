# -*- coding: utf-8 -*-
from imio.esign import _
from imio.esign.browser.table import external_session_link
from imio.esign.browser.table import SessionsTable
from imio.esign.utils import create_external_session
from imio.esign.utils import get_session_annotation
from imio.esign.utils import remove_session
from imio.helpers.content import uuidToObject
from imio.prettylink.interfaces import IPrettyLink
from plone import api
from plone.app.layout.viewlets import ViewletBase
from Products.Five import BrowserView
from zope.browserpage.viewpagetemplatefile import ViewPageTemplateFile

import os


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


def get_microservice_credentials(self):
    """Get the credentials to connect to microservice."""
    # get it from environment variable
    return os.getenv("ESIGN_CREDENTIALS", "")


def get_esign_root_url(self):
    """Get the esign root url to connect to microservice."""
    return os.getenv("ESIGN_ROOT_URL", "")


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
            b64_cred=get_microservice_credentials(),
            esign_root_url=get_esign_root_url()
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
