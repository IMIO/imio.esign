# -*- coding: utf-8 -*-
from imio.esign import _
from imio.esign.adapters import ISignable
from imio.esign.utils import add_files_to_session
from imio.esign.utils import remove_context_from_session
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
        # observers = self.get_observers()
        add_files_to_session(
            signers=signers,
            # observers=observers,
            files_uids=files_uids,
            title=self.get_session_title(),
            discriminators=self.get_discriminators(),
        )
        self._finished()

    def _get_signers(self, show_message=True):
        """Get the list of held_positions to be used as signer.

        :return: list of signer infos with "held_position", "name" and "function"
        """
        res = []
        for signer_info in ISignable(self.context).get_signers():
            if not signer_info["held_position"]:
                if show_message is True:
                    api.portal.show_message(
                        _(
                            "Problem with certified signatories, make sure a held position "
                            'is selected for each signatory (check "${name}/${function}")!',
                            mapping={"name": signer_info["name"], "function": signer_info["function"]},
                        ),
                        request=self.request,
                        type="warning",
                    )
                return []
            res.append(signer_info)
        return res

    def get_signers(self):
        """List of signers, should not be overrided, rely on self._get_signers.

        :return: list of signer infos (userid, email, fullname, position)
        """
        res = []
        signer_infos = self._get_signers()
        # signers is a list of held_positions
        for signer_info in signer_infos:
            # get email from user
            hp = signer_info["held_position"]
            signer_person = hp.get_person()
            userid = signer_person.userid
            user = api.user.get(userid)
            email = user.getProperty("email")
            person_title = signer_info["name"] or signer_person.get_title(include_person_title=False)
            hp_label = signer_info["function"] or hp.label or u""
            res.append((userid, email, person_title, hp_label))
        return tuple(res)

    def get_observers(self):
        """List of observers."""
        return ()

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
        return ()


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
