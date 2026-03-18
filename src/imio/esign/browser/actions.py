# -*- coding: utf-8 -*-
from AccessControl import Unauthorized
from html import escape
from imio.esign import _
from imio.esign.adapters import ISignable
from imio.esign.utils import add_files_to_session
from imio.esign.utils import get_session_annotation
from imio.esign.utils import persistent_to_native
from imio.esign.utils import remove_context_from_session
from imio.esign.utils import remove_files_from_session
from imio.helpers.content import uuidToObject
from imio.helpers.security import check_zope_admin
from plone import api
from Products.CMFPlone.utils import safe_unicode
from Products.Five import BrowserView
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile

import pprint
import re


class AddToSessionView(BrowserView):
    """View to add an element to an esign session."""

    def __init__(self, context, request):
        super(AddToSessionView, self).__init__(context, request)

    def _finished(self, failed_msgid="", mapping={}):
        msgid = "Element added to session!"
        msg_type = "info"
        if failed_msgid:
            msgid = failed_msgid
            msg_type = "warning"
        api.portal.show_message(_(msgid, mapping=mapping), request=self.request, type=msg_type)
        self.request.RESPONSE.redirect(self.context.absolute_url())

    def index(self):
        files_uids = ISignable(self.context).get_files_uids()
        if not files_uids:
            return self._finished(failed_msgid="Could not get files uids to add to the session!")
        signers = self.get_signers()
        if not signers:
            return self._finished(failed_msgid="Could not get signers to add to the session!")
        # watchers = self.get_watchers()
        add_files_to_session(
            signers=signers,
            # watchers=watchers,
            files_uids=files_uids,
            title=self.get_session_title(),
            watchers=self.get_watchers(),
            discriminators=self.get_discriminators(),
        )
        self._finished()

    def get_signers(self):
        """Get the list of held_positions to be used as signer.

        :return: list of signer infos with "held_position", "name",
                 "function", "userid" and "email"
        """
        try:
            signers = ISignable(self.context).get_signers()
        except ValueError as msg:
            signers = []
            api.portal.show_message(
                _(
                    "Problem getting signers: \"${error}\")!",
                    mapping={"error": str(msg)},
                ),
                request=self.request,
                type="warning",
            )
        return signers

    def get_watchers(self):
        """List of watchers email."""
        return ISignable(self.context).get_watchers()

    def get_context_uid(self):
        """ """
        return self.context.UID()

    def get_session_title(self):
        """The title for the session.

        :return: a string with informative session title
        """
        return "Session title"

    def get_discriminators(self):
        """ """
        return ISignable(self.context).get_discriminators()


class RemoveFromSessionView(BrowserView):
    """View to remove an element from an esign session."""

    def __init__(self, context, request):
        super(RemoveFromSessionView, self).__init__(context, request)

    def _finished(self):
        msg = _("Element removed from session!")
        api.portal.show_message(msg, request=self.request)
        self.request.RESPONSE.redirect(self.context.absolute_url())

    def index(self):
        remove_context_from_session(context_uids=[self.get_uid_to_remove()])
        self._finished()

    def get_uid_to_remove(self):
        """ """
        return self.context.UID()

    def available(self):
        """Defines if the action is available or not."""
        annot = get_session_annotation()
        return self.context.UID() in annot.get("c_uids", {})


class RemoveItemFromSessionView(BrowserView):
    """View to remove an item from an esign session."""

    def __init__(self, context, request):
        super(RemoveItemFromSessionView, self).__init__(context, request)

    def _finished(self):
        msg = _("Element removed from session!")
        api.portal.show_message(msg, request=self.request)
        self.request.RESPONSE.redirect(self.context.absolute_url())

    def index(self):
        remove_files_from_session(files_uids=[self.context.UID()])
        self._finished()

    def available(self):
        """Defines if the action is available or not."""
        annot = get_session_annotation()
        return self.context.UID() in annot.get("uids", {})


class SessionAnnotationInfoView(BrowserView):
    """Admin-only view displaying imio.esign session annotations for a specific context item."""

    index = ViewPageTemplateFile("templates/session_annotation_info.pt")

    def __call__(self):
        if not check_zope_admin():
            raise Unauthorized
        return self.index()

    def _uid_to_link(self, uid):
        """Return an HTML link for an object UID, or the UID if not found."""
        obj = uuidToObject(uid, unrestricted=True)
        if obj is None:
            return u"<span title='not found'>{}</span>".format(safe_unicode(uid))
        url = escape(obj.absolute_url() + "/view", quote=True)
        path = escape(u"/".join(obj.getPhysicalPath()))
        title = escape(safe_unicode(getattr(obj, "title", "") or path))
        return u"<a href='{}' title='{}'>{}</a>".format(url, path, title)

    def _render_value(self, value, indent=u""):
        """Render a value, replacing UIDs with links where possible."""
        inner = indent + u"  "
        if isinstance(value, dict):
            if not value:
                return u"{}"
            lines = [u"{"]
            for k, v in sorted(value.items()):
                key = escape(safe_unicode(pprint.pformat(k)))
                lines.append(u"{}{}: {},".format(inner, key, self._render_value(v, inner)))
            lines.append(u"{}}}".format(indent))
            return u"\n".join(lines)
        elif isinstance(value, (list, tuple)):
            if not value:
                return u"[]"
            lines = [u"["]
            for item in value:
                lines.append(u"{}{},".format(inner, self._render_value(item, inner)))
            lines.append(u"{}]".format(indent))
            return u"\n".join(lines)
        elif isinstance(value, basestring) and re.match(r"^[0-9a-f]{32}$", value):
            # Looks like a UUID
            return self._uid_to_link(value)
        else:
            return escape(safe_unicode(pprint.pformat(value)))

    @property
    def esign_sessions(self):
        """
        Return list of (session_id, session_data) for all sessions.
        Filter sessions using request params "session_id" and "context_uid" if provided.
        Returns all sessions if no filter params provided.
        """
        annot = get_session_annotation()
        request_session_id = self.request.form.get("session_id")
        try:
            request_session_id = int(request_session_id)
        except (ValueError, TypeError):
            request_session_id = None

        c_uid = self.request.form.get("context_uid")
        result = []
        for session_id in annot['sessions']:
            if request_session_id is not None and request_session_id != session_id:
                continue
            session = annot.get("sessions", {}).get(session_id)
            # If any file in this session is in this context
            if c_uid and not any(f['context_uid'] == c_uid for f in session['files']):
                continue
            result.append((session_id, persistent_to_native(session)))
        return sorted(result)

    def esign_session_html(self, session_data):
        """Renders esign session annot in HTML"""
        return self._render_value(session_data)
