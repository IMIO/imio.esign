# -*- coding: utf-8 -*-
from plone.app.robotframework.testing import REMOTE_LIBRARY_BUNDLE_FIXTURE
from plone.app.testing import applyProfile
from plone.app.testing import FunctionalTesting
from plone.app.testing import IntegrationTesting
from plone.app.testing import PLONE_FIXTURE
from plone.app.testing import PloneSandboxLayer
from plone.testing import z2

import imio.esign  # noqa: F401


class ImioEsignLayer(PloneSandboxLayer):

    defaultBases = (PLONE_FIXTURE,)

    def setUpZope(self, app, configurationContext):
        # Load any other ZCML that is required for your tests.
        # The z3c.autoinclude feature is disabled in the Plone fixture base
        # layer.
        import plone.app.dexterity

        self.loadZCML(package=plone.app.dexterity)
        import plone.restapi

        self.loadZCML(package=plone.restapi)
        import imio.annex

        self.loadZCML(package=imio.annex)
        self.loadZCML(package=imio.esign)

    def setUpPloneSite(self, portal):
        applyProfile(portal, "imio.annex:default")
        applyProfile(portal, "imio.esign:default")


IMIO_ESIGN_FIXTURE = ImioEsignLayer()


IMIO_ESIGN_INTEGRATION_TESTING = IntegrationTesting(
    bases=(IMIO_ESIGN_FIXTURE,),
    name="ImioEsignLayer:IntegrationTesting",
)


IMIO_ESIGN_FUNCTIONAL_TESTING = FunctionalTesting(
    bases=(IMIO_ESIGN_FIXTURE,),
    name="ImioEsignLayer:FunctionalTesting",
)


IMIO_ESIGN_ACCEPTANCE_TESTING = FunctionalTesting(
    bases=(
        IMIO_ESIGN_FIXTURE,
        REMOTE_LIBRARY_BUNDLE_FIXTURE,
        z2.ZSERVER_FIXTURE,
    ),
    name="ImioEsignLayer:AcceptanceTesting",
)
