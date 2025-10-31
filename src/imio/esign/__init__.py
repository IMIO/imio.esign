# -*- coding: utf-8 -*-
"""Init and utils."""
from plone import api
from zope.component import queryUtility
from zope.i18n import ITranslationDomain
from zope.i18nmessageid import MessageFactory

import os


_ = MessageFactory("imio.esign")
PLONE_VERSION = int(api.env.plone_version()[0])
ESIGN_ROOT_URL = os.getenv("ESIGN_ROOT_URL", "http://127.0.0.1:8000")
ESIGN_CREDENTIALS = os.getenv("ESIGN_CREDENTIALS", "")


def _tr(msgid, domain="imio.esign", mapping=None):
    translation_domain = queryUtility(ITranslationDomain, domain)
    return translation_domain.translate(msgid, target_language=api.portal.get_current_language(), mapping=mapping)
