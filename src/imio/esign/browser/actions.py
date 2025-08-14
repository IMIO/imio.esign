# -*- coding: utf-8 -*-
from collective.iconifiedcategory.utils import get_categorized_elements
from imio.esign import _
from imio.esign.utils import add_files_to_session
# from imio.esign.utils import remove_files_from_session
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
        files_uids = self.get_files_uids()
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

    def _get_signers(self):
        """Get the list of held_positions to be used as signer.

        :return: list of held_position objects
        """
        res = []
        # make sure signers are sorted by signature number
        for signer_number, signer_infos in sorted(self.context.getCertifiedSignatures(listify=False).items()):
            if not signer_infos["held_position"]:
                api.portal.show_message(
                    _(
                        "Problem with certified signatories, make sure a held position "
                        'is selected for each signatory (check "${name}/${function}")!',
                        mapping={"name": signer_infos["name"], "function": signer_infos["function"]},
                    ),
                    request=self.request,
                    type="warning",
                )
                return []
            res.append(signer_infos["held_position"])
        return res

    def get_signers(self):
        """List of signers, should not be overrided, rely on self._get_signers.

        :return: list of signer infos (userid, email, fullname, position)
        """
        res = []
        signers = self._get_signers()
        # signers is a list of held_positions
        for hp in signers:
            userid = hp.userid or ""
            user = api.user.get(userid)
            if not userid or not user:
                api.portal.show_message(
                    _(
                        'Problem with "userid" defined for "held_position" at "${held_position_url}!"',
                        mapping={"held_position_url": hp.absolute_url()},
                    ),
                    request=self.request,
                    type="warning",
                )
                return ()
            # get email from user
            email = user.getProperty("email")
            person_title = hp.get_person().get_title(include_person_title=False)
            hp_title = hp.get_title()
            res.append((userid, email, person_title, hp_title))
        return tuple(res)

    def get_observers(self):
        """List of observers."""
        return ()

    def get_context_uid(self):
        """ """
        return self.context.UID()

    def get_files_uids(self):
        """List of file uids.

        :return: list of uid of files marked as "to_sign/True" but "signed/False"
        """
        return [
            elt["UID"] for elt in get_categorized_elements(self.context, filters={"to_sign": True, "signed": False})
        ]

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
        super(AddToSessionView, self).__init__(context, request)

    def _finished(self):
        msg = _("Element removed from session!", context=self.request)
        api.portal.show_message(msg, request=self.request)
        self.request.RESPONSE.redirect(self.context.absolute_url())

    def index(self):
        # remove_files_from_session(
        #     uid=self.get_uid_to_remove())
        self._finished()

    def get_uid_to_remove(self):
        """ """
        return self.context.UID()
