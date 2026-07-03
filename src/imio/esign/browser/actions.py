# -*- coding: utf-8 -*-
from AccessControl import Unauthorized
from html import escape
from imio.esign import _
from imio.esign import manage_session_perm
from imio.esign.adapters import ISignable
from imio.esign.audit import audit
from imio.esign.browser.views import SessionFilesMixin
from imio.esign.utils import add_files_to_session
from imio.esign.utils import create_session
from imio.esign.utils import get_session_annotation
from imio.esign.utils import get_sessions_for
from imio.esign.utils import persistent_to_native
from imio.esign.utils import remove_context_from_session
from imio.esign.utils import remove_files_from_session
from imio.helpers.content import uuidToObject
from imio.helpers.security import check_zope_admin
from plone import api
from Products.CMFPlone.utils import safe_unicode
from Products.Five import BrowserView
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile
from six import string_types
from zope.i18n import translate

import json
import pprint
import re


class AddToSessionView(BrowserView):
    """View to add an element to an esign session."""

    def __init__(self, context, request):
        super(AddToSessionView, self).__init__(context, request)

    def _finished(self, failed_msgid="", mapping={}):
        msgid = "Element added to session(s) ${session_ids}!"
        msg_type = "info"
        if failed_msgid:
            msgid = failed_msgid
            msg_type = "warning"
        api.portal.show_message(_(msgid, mapping=mapping), request=self.request, type=msg_type)
        self.request.RESPONSE.redirect(self.request['HTTP_REFERER'])

    def index(self):
        files_uids = ISignable(self.context).get_files_uids()
        if not files_uids:
            return self._finished(failed_msgid="Could not get files uids to add to the session!")
        signers = self.get_signers()
        if not signers:
            return self._finished(failed_msgid="Could not get signers to add to the session!")
        # watchers = self.get_watchers()
        session_ids = add_files_to_session(
            signers=signers,
            # watchers=watchers,
            files_uids=files_uids,
            title=self.get_session_title(),
            watchers=self.get_watchers(),
            discriminators=self.get_discriminators(),
        )
        # audit("add_to_session", "session={} context={} files={} signers={}".format(
        #     session_id, self.context.UID(), ",".join(files_uids), len(signers)))
        self._finished(mapping={"session_ids": u", ".join([tup[0] for tup in session_ids])})

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
        self.request.RESPONSE.redirect(self.request['HTTP_REFERER'])

    def index(self):
        uid = self.get_uid_to_remove()
        str_session_ids = ",".join([str(sid) for sid in get_sessions_for(uid).keys()])
        remove_context_from_session(context_uids=[uid])
        audit("remove_context_from_session", "sessions={} context={}".format(str_session_ids, uid))
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
        self.request.RESPONSE.redirect(self.request['HTTP_REFERER'])

    def index(self):
        uid = self.context.UID()
        session_id = get_session_annotation().get("uids", {}).get(uid)
        remove_files_from_session(files_uids=[uid])
        audit("remove_item_from_session", "session={} file={}".format(session_id, uid))
        self._finished()

    def available(self):
        """Defines if the action is available or not."""
        annot = get_session_annotation()
        return self.context.UID() in annot.get("uids", {})


class SessionAnnotationInfoView(BrowserView):
    """Admin-only view displaying imio.esign session annotations for a specific context item."""

    index = ViewPageTemplateFile("templates/session_annotation_info.pt")

    def __call__(self):
        if not self.available():
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
        return u"<a href='{}' title='{}'>{}</a> ({})".format(url, path, title, uid)

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
        elif isinstance(value, string_types) and re.match(r"^[0-9a-f]{32}$", value):
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
            session = annot['sessions'][session_id]
            # If any file in this session is in this context
            if c_uid and not any(f['context_uid'] == c_uid for f in session['files']):
                continue
            result.append((session_id, persistent_to_native(session)))
        return sorted(result)

    def esign_session_html(self, session_data):
        """Renders esign session annot in HTML"""
        return self._render_value(session_data)

    def available(self):
        """Defines if the action is available or not."""
        return check_zope_admin()


class _RecreateSessionMixin(object):
    """Shared permission check for the recreate views."""

    def may_recreate_session(self):
        """Check if the user may recreate sessions."""
        return api.user.has_permission(manage_session_perm, obj=self.context)


class RecreateSessionView(_RecreateSessionMixin, BrowserView):
    """Admin view to recreate a fresh draft session from an existing non-draft session."""

    _new_session_id = None

    def __call__(self):
        if not self.may_recreate_session():
            raise Unauthorized
        session_id = self.request.form.get("esign_session_id")
        if not session_id:
            api.portal.show_message(_("No session ID provided!"), request=self.request, type="error")
            return self.context.absolute_url() + "/@@parapheo"
        if not session_id.isdigit():
            api.portal.show_message(_("Invalid session ID!"), request=self.request, type="error")
            return self.context.absolute_url() + "/@@parapheo"
        session_id = int(session_id)
        annot = get_session_annotation()
        sessions = annot["sessions"]
        if session_id not in sessions:
            api.portal.show_message(_("Session not found!"), request=self.request, type="error")
            return self.context.absolute_url() + "/@@parapheo"
        old = sessions[session_id]
        if old["state"] == "draft":
            api.portal.show_message(_("Cannot recreate a draft session!"), request=self.request, type="warning")
            return self.context.absolute_url() + "/@@parapheo"
        # Extract all data from old session before deleting it
        signers = [(s["userid"], s["email"], s["fullname"], s["position"]) for s in old["signers"]]
        files_uids = [f["uid"] for f in old["files"]]
        raw_selection = self.request.form.get("file_uids", None)
        if raw_selection is not None:
            try:
                selected = set(json.loads(raw_selection or "[]"))
            except (ValueError, TypeError):
                selected = set()
            files_uids = [uid for uid in files_uids if uid in selected]
            if not files_uids:
                api.portal.show_message(_("No file selected!"), request=self.request, type="warning")
                return self.context.absolute_url() + "/@@parapheo"
        seal = old.get("seal")
        acroform = old.get("acroform", True)
        discriminators = old.get("discriminators", ())
        title = old.get("title", u"")
        watchers = list(old.get("watchers", []))
        # Remove selected files from the old session
        remove_files_from_session(files_uids)
        # Create new draft session (call create_session directly to bypass discriminate_sessions)
        new_id, _new_session = create_session(
            signers=signers,
            seal=seal,
            acroform=acroform,
            title=title,
            annot=annot,
            discriminators=discriminators,
            watchers=watchers,
            create_session_custom_data={"recreated_from": session_id},
        )
        add_files_to_session(
            signers=signers,
            files_uids=files_uids,
            session_id=new_id,
        )
        self._new_session_id = new_id
        audit(
            "recreate_session",
            "old_session={} new_session={} files={}".format(session_id, new_id, len(files_uids)),
        )
        api.portal.show_message(
            _("New session ${nid} created from session ${oid}", mapping={"nid": new_id, "oid": session_id}),
            request=self.request,
            type="info",
        )
        return self.context.absolute_url() + "/@@parapheo"


class RecreateSessionFormView(_RecreateSessionMixin, SessionFilesMixin, BrowserView):
    """Overlay form to choose which files to include when recreating a session."""

    index = ViewPageTemplateFile("templates/recreate_session_form.pt")
    session_id = None
    _session = None

    def __call__(self):
        if not self.may_recreate_session():
            raise Unauthorized
        session_id = self.request.form.get("esign_session_id")
        if not session_id or not session_id.isdigit():
            return self._error(_("Invalid session ID!"))
        session_id = int(session_id)
        session = get_session_annotation()["sessions"].get(session_id)
        if session is None:
            return self._error(_("Session not found!"))
        if session["state"] == "draft":
            return self._error(_("Cannot recreate a draft session!"))
        self.session_id = session_id
        self._session = session
        return self.index()

    def _error(self, msg):
        """Render a standalone error message inside the overlay."""
        return u'<div class="portalMessage error">{}</div>'.format(translate(msg, context=self.request))

    def files(self):
        """The (context, file) object pairs of the session"""
        return self.resolve_session_files(self._session)

    def no_file_msg(self):
        """Translated alert shown when the user submits with no file selected."""
        return translate(_("Please select at least one file."), context=self.request)

    def recreate_onclick(self):
        """JS run by the Recreate button: collect checked files then reload.

        Built here (not in the template) so the many semicolons don't collide
        with the ``tal:attributes`` separator.
        """
        js = (
            "var u=Array.prototype.map.call("
            "this.closest('.recreate-session-form').querySelectorAll('.recreate-file-cb:checked'),"
            "function(c){return c.value;});"
            "if(!u.length){alert('%(msg)s');return;}"
            "callViewAndReload('%(base)s','@@esign-session-recreate',"
            "{'esign_session_id':'%(sid)s','file_uids':JSON.stringify(u)});"
        ) % {
            "msg": self.no_file_msg().replace(u"'", u"\\'"),
            "base": self.context.absolute_url(),
            "sid": self.session_id,
        }
        return js

    def refused_reason(self):
        """Refusal reason for a refused session, else an empty string.

        The reason is stored by the external feedback service in the "returns"
        list, on the code 52 (document_declined) entry, as ``value["reason"]``.
        """
        if not self._session or self._session.get("state") != "refused":
            return u""
        for entry in reversed(list(self._session.get("returns", []))):
            if entry and entry[0] == 52 and isinstance(entry[2], dict):
                return entry[2].get("reason", u"") or u""
        return u""
