# -*- coding: utf-8 -*-
"""Init and utils."""
from plone import api
from zope.i18nmessageid import MessageFactory


_ = MessageFactory("imio.esign")
PLONE_VERSION = int(api.env.plone_version()[0])
E_SIGN_ROOT_URL = "http://127.0.0.1:8000"
