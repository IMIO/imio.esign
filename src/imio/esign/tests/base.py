# -*- coding: utf-8 -*-
"""Shared base test class for imio.esign tests."""
from imio.esign.testing import IMIO_ESIGN_INTEGRATION_TESTING
from plone.app.testing import login
from plone.app.testing import setRoles
from plone.app.testing import TEST_USER_ID
from plone.app.testing import TEST_USER_NAME
from zope.component import getGlobalSiteManager
from zope.schema.interfaces import IVocabularyFactory
from zope.schema.vocabulary import SimpleTerm
from zope.schema.vocabulary import SimpleVocabulary

import os
import unittest


TESTS_DIR = os.path.dirname(__file__)


class BaseEsignTest(unittest.TestCase):
    """Base class: shared layer, minimal setUp, and optionnal helpers."""

    layer = IMIO_ESIGN_INTEGRATION_TESTING

    def setUp(self):
        self.portal = self.layer["portal"]
        self.request = self.layer["request"]
        self.request.form.clear()
        setRoles(self.portal, TEST_USER_ID, ["Manager"])
        login(self.portal, TEST_USER_NAME)

    def register_signers(self, *userids):
        """Make the given userids the signers listed by the imio.esign.signers vocabulary."""
        vocab = SimpleVocabulary([SimpleTerm(uid, uid, uid.upper()) for uid in userids])
        gsm = getGlobalSiteManager()  # not persisted, unlike the site manager, so a lambda can be registered
        name = "imio.esign.signers"
        self.addCleanup(gsm.registerUtility, gsm.getUtility(IVocabularyFactory, name), IVocabularyFactory, name)
        gsm.registerUtility(lambda context: vocab, IVocabularyFactory, name)
