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
