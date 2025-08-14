from imio.esign.browser.views import DUMMY_SESSIONS

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

    @property
    def query_session_files(self):
        if "esign_session_id[]" in self.request.form.keys():
            session_id = self.request.form["esign_session_id[]"]
        else:
            session_id = self.request.get("esign_session_id", None)
        if not session_id:
            return {"UID": {"query": []}}
        session = self.get_session(session_id)
        obj_uids = []
        for f in session.get("files", []):
            obj_uids.append(f["context_uid"])
        return {"UID": {"query": obj_uids}}

    def get_session(self, session_id):
        return DUMMY_SESSIONS["sessions"].get(int(session_id), {})

    query = query_session_files
