# -*- coding: utf-8 -*-

from imio.esign import logger
from imio.esign.interfaces import IImioSessionsManagementContext
from plone import api
from Products.CMFPlone.interfaces import INonInstallable
from zope.interface import alsoProvides
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
    portal = api.portal.get()
    create_sessions_link(portal)


def uninstall(context):
    """Uninstall script"""
    # Do something at the end of the uninstallation of this package.


def create_sessions_link(portal):
    """Create sessions link in portal root if not exists"""
    if not hasattr(portal, "sessions"):
        portal.invokeFactory("Link", id="sessions", title="Sessions", remoteUrl="sessions/esign-sessions-listing")
        s_l = portal["sessions"]
        s_l.setExcludeFromNav(True)
        alsoProvides(s_l, IImioSessionsManagementContext)
        # alsoProvides(s_l, IProtectedItem)
        s_l.manage_permission("Access contents information",
                              ("Contributor", "Editor", "Manager", "Reader", "Site administrator"), acquire=0)
        s_l.manage_permission("Modify portal content", ("Owner", ), acquire=0)
        s_l.manage_permission("View", ("Contributor", "Editor", "Manager", "Reader", "Site administrator"), acquire=0)
        s_l.changeOwnership(s_l.portal_membership.getMemberById("admin"))
        s_l.reindexObject()

        unlisted = list(portal.portal_properties.navtree_properties.metaTypesNotToList)
        if "Link" not in unlisted:
            unlisted.append("Link")
            portal.portal_properties.navtree_properties.manage_changeProperties(metaTypesNotToList=unlisted)
        logger.info("Sessions link created in portal root")
