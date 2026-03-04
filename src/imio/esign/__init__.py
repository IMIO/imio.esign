# -*- coding: utf-8 -*-
"""Init and utils."""
from imio.fpaudit import utils as _fpaudit_utils
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
manage_session_perm = "imio.esign: Manage Sessions"

if os.environ.get("ZOPE_HOME") is None:  # test env
    logged_actions = []

    def mock_fplog(log_id, action, extras):
        logged_actions.append((log_id, action, extras))

    logger.warn("PATCHING imio.fpaudit.utils.fplog")
    _fpaudit_utils.fplog = mock_fplog


def _tr(msgid, domain="imio.esign", mapping=None):
    translation_domain = queryUtility(ITranslationDomain, domain)
    return translation_domain.translate(msgid, target_language=api.portal.get_current_language(), mapping=mapping)
