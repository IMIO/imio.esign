# -*- coding: utf-8 -*-
"""Shared base test class for imio.esign tests."""
from imio.esign.testing import IMIO_ESIGN_INTEGRATION_TESTING
from plone.app.testing import login
from plone.app.testing import setRoles
from plone.app.testing import TEST_USER_ID
from plone.app.testing import TEST_USER_NAME
from Products.statusmessages import STATUSMESSAGEKEY
from zope.annotation.interfaces import IAnnotations

import os
import unittest


TESTS_DIR = os.path.dirname(__file__)


def clear_status_messages(request):
    """Clear status messages from request annotations (needed after redirects since show() skips clearing on 3xx)."""
    annotations = IAnnotations(request)
    annotations[STATUSMESSAGEKEY] = None
    request.response.expireCookie(STATUSMESSAGEKEY, path="/")


class BaseEsignTest(unittest.TestCase):
    """Base class: shared layer, minimal setUp, and optionnal helpers."""

    layer = IMIO_ESIGN_INTEGRATION_TESTING

    def setUp(self):
        self.portal = self.layer["portal"]
        self.request = self.layer["request"]
        self.request.form.clear()
        setRoles(self.portal, TEST_USER_ID, ["Manager"])
        login(self.portal, TEST_USER_NAME)
