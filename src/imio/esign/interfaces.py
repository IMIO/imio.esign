# -*- coding: utf-8 -*-
"""Module where all interfaces, events and exceptions live."""

from zope.interface import Interface
from zope.publisher.interfaces.browser import IDefaultBrowserLayer


class IImioEsignLayer(IDefaultBrowserLayer):
    """Marker interface that defines a browser layer."""


class IContextUidProvider(Interface):
    """Adapter to provide context UID for a file."""

    def get_context_uid():
        """Return the context UID for the file to sign."""


class IItemOrderProvider(Interface):
    """Adapter to provide item ordering within a context."""

    def get_item_order():
        """Return a dict mapping item UID to sort position (int).
        Items not in the dict get position -1.
        """
