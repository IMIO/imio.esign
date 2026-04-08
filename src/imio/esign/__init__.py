# -*- coding: utf-8 -*-
"""Init and utils."""
from plone import api
from zope.component import queryUtility
from zope.i18n import ITranslationDomain
from zope.i18nmessageid import MessageFactory

import logging
import os


_ = MessageFactory("imio.esign")
logger = logging.getLogger("imio.esign")
PLONE_VERSION = int(api.env.plone_version()[0])
API_ROOT_URL = os.getenv("API_ROOT_URL", "http://127.0.0.1:8000")
CLEANUP_THROTTLE_HOURS = 24
manage_session_perm = "imio.esign: Manage Sessions"


def _tr(msgid, domain="imio.esign", mapping=None):
    translation_domain = queryUtility(ITranslationDomain, domain)
    return translation_domain.translate(msgid, target_language=api.portal.get_current_language(), mapping=mapping)
