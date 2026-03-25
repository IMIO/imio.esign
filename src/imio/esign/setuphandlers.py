# -*- coding: utf-8 -*-
from imio.esign.audit import LOG_ID
from imio.esign.config import get_registry_parapheo_url
from imio.esign.config import get_registry_signing_users_email_content
from imio.esign.config import set_registry_parapheo_url
from imio.esign.config import set_registry_signing_users_email_content
from imio.esign.config import SIGNERS_EMAIL_CONTENT
from plone.registry.interfaces import IRegistry
from Products.CMFPlone.interfaces import INonInstallable
from zope.component import getUtility
from zope.interface import implementer


@implementer(INonInstallable)
class HiddenProfiles(object):
    def getNonInstallableProfiles(self):
        """Hide uninstall profile from site-creation and quickinstaller."""
        return [
            "imio.esign:uninstall",
        ]

    def getNonInstallableProducts(self):
        """Hide the upgrades package from site-creation and quickinstaller."""
        return ["imio.esign.upgrades"]


def post_install(context):
    """Post install script"""
    if not get_registry_parapheo_url():
        set_registry_parapheo_url(u"https://simplycosi-1-test.trustsigneurope.com/login?tenantName=IMIO")
    if not get_registry_signing_users_email_content():
        set_registry_signing_users_email_content(SIGNERS_EMAIL_CONTENT)
    configure_fpaudit()


def configure_fpaudit():
    """Add esign audit log entry to imio.fpaudit registry if not already present."""
    registry = getUtility(IRegistry)
    entries = list(registry.get("imio.fpaudit.settings.log_entries") or [])
    if not any(e.get("log_id") == LOG_ID for e in entries):
        entries.append({u"log_id": LOG_ID, u"audit_log": u"esign.log",
                        u"log_format": u"%(asctime)s - %(message)s"})
        registry["imio.fpaudit.settings.log_entries"] = entries


def uninstall(context):
    """Uninstall script"""
    # Do something at the end of the uninstallation of this package.
