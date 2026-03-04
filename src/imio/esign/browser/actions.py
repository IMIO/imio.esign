# -*- coding: utf-8 -*-
from imio.esign import _
from imio.esign.adapters import ISignable
from imio.esign.audit import audit
from imio.esign.utils import add_files_to_session
from imio.esign.utils import get_session_annotation
from imio.esign.utils import remove_context_from_session
from imio.esign.utils import remove_files_from_session
from plone import api
from Products.Five import BrowserView


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
        session_id, _session = add_files_to_session(
            signers=signers,
            # watchers=watchers,
            files_uids=files_uids,
            title=self.get_session_title(),
            watchers=self.get_watchers(),
            discriminators=self.get_discriminators(),
        )
        audit("add_to_session", "session={} context={} files={} signers={}".format(
            session_id, self.context.UID(), len(files_uids), len(signers)))
        self._finished()

    def get_signers(self):
        """Get the list of held_positions to be used as signer.

        :return: list of signer infos with "held_position", "name",
                 "function", "userid" and "email"
        """
        try:
            signers = ISignable(self.context).get_signers()
        except ValueError, msg:
            signers = []
            api.portal.show_message(
                _(
                    "Problem getting signers: \"${error}\")!",
                    mapping={"error": msg},
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
        uid = self.get_uid_to_remove()
        annot = get_session_annotation()
        file_uids = annot.get("c_uids", {}).get(uid, [])
        session_id = annot.get("uids", {}).get(file_uids[0]) if file_uids else None
        remove_context_from_session(context_uids=[uid])
        audit("remove_context_from_session", "session={} context={}".format(session_id, uid))
        self._finished()

    def get_uid_to_remove(self):
        """ """
        return self.context.UID()


class RemoveItemFromSessionView(BrowserView):
    """View to remove an item from an esign session."""

    def __init__(self, context, request):
        super(RemoveItemFromSessionView, self).__init__(context, request)

    def _finished(self):
        msg = _("Element removed from session!")
        api.portal.show_message(msg, request=self.request)
        self.request.RESPONSE.redirect(self.context.absolute_url())

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
