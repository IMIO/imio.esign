from imio.esign.utils import get_session_annotation
from plone.memoize import ram
from zope.interface import Interface


class DefaultContextUidProvider(object):
    """Default adapter that returns parent UID as context."""

    def __init__(self, context):
        self.context = context

    def get_context_uid(self):
        """Return parent UID as default context."""
        parent = getattr(self.context, "aq_parent", None)
        if parent and hasattr(parent, "UID"):
            return parent.UID()
        return None


class FilesBelongingToAGivenSession(object):
    def __init__(self, context):
        self.context = context
        self.request = self.context.REQUEST

    def query_session_files_cachekey(method, self):
        return (get_session_annotation()._p_mtime, self.get_session_id())

    @property
    @ram.cache(query_session_files_cachekey)
    def query_session_files(self):
        session_id = self.get_session_id()
        if not session_id:
            return {"UID": {"query": []}}
        session = self.get_session(session_id)
        obj_uids = []
        for f in session.get("files", []):
            obj_uids.append(f["context_uid"])
        return {"UID": {"query": obj_uids}}

    def get_session_id(self):
        if "esign_session_id[]" in self.request.form.keys():
            return self.request.form["esign_session_id[]"]
        else:
            return self.request.get("esign_session_id", None)

    def get_session(self, session_id=None):
        if session_id is None:
            session_id = self.get_session_id()
        return get_session_annotation()["sessions"].get(int(session_id), {})

    query = query_session_files


class ISignable(Interface):
    def get_signers(self):
        """
        List signers for that item.
        returns a list of dict with keys: name, function, held_position
        """

    def get_files_uids(self):
        """
        List of file uids to sign.
        """
