# -*- coding: utf-8 -*-
"""Init and utils."""
from plone import api
from zope.i18nmessageid import MessageFactory


_ = MessageFactory("imio.esign")
PLONE_VERSION = int(api.env.plone_version()[0])
