# -*- coding: utf-8 -*-
from imio.fpaudit.utils import fpalog


LOG_ID = u"esign"


def audit(action, extras=""):
    """Log an eSignature action to the dedicated audit log."""
    fpalog(LOG_ID, action, extras)
