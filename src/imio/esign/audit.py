# -*- coding: utf-8 -*-
from imio.fpaudit import utils as fpaudit_utils


LOG_ID = u"esign"


def audit(action, extras=""):
    """Log an eSignature action to the dedicated audit log."""
    fpaudit_utils.fplog(LOG_ID, action, extras)
