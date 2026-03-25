# -*- coding: utf-8 -*-
from imio.fpaudit import utils as _fpaudit_utils  # import module so it can be patched in a second time


LOG_ID = u"esign"


def audit(action, extras=""):
    """Log an eSignature action to the dedicated audit log."""
    _fpaudit_utils.fpalog(LOG_ID, action, extras)
