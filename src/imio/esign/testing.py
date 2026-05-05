# -*- coding: utf-8 -*-
from collective.iconifiedcategory.utils import calculate_category_id
from imio.fpaudit import utils as _fpaudit_utils
from plone import api
from plone.app.robotframework.testing import REMOTE_LIBRARY_BUNDLE_FIXTURE
from plone.app.testing import applyProfile
from plone.app.testing import FunctionalTesting
from plone.app.testing import IntegrationTesting
from plone.app.testing import login
from plone.app.testing import PLONE_FIXTURE
from plone.app.testing import PloneSandboxLayer
from plone.app.testing import setRoles
from plone.app.testing import TEST_USER_ID
from plone.app.testing import TEST_USER_NAME
from plone.namedfile.file import NamedBlobFile
from plone.namedfile.file import NamedBlobImage
from plone.testing import z2
from zope.globalrequest import setLocal

import imio.esign  # noqa: F401
import os


logged_actions = []


def _mock_fpalog(log_id, action, extras):
    logged_actions.append(extras)


_fpaudit_utils.fpalog = _mock_fpalog


class ImioEsignLayer(PloneSandboxLayer):

    defaultBases = (PLONE_FIXTURE,)

    def setUpZope(self, app, configurationContext):
        import plone.app.dexterity

        self.loadZCML(package=plone.app.dexterity)
        import plone.restapi

        self.loadZCML(package=plone.restapi)
        import imio.annex

        self.loadZCML(package=imio.annex)
        self.loadZCML(package=imio.esign)

    def setUpPloneSite(self, portal):
        setLocal("request", portal.REQUEST)
        applyProfile(portal, "imio.annex:default")
        applyProfile(portal, "imio.esign:default")
        setRoles(portal, TEST_USER_ID, ["Manager"])
        login(portal, TEST_USER_NAME)
        self._setup_content_categories(portal)
        self._setup_shared_content(portal)

    def _setup_content_categories(self, portal):
        """
        Creates: portal/annexes_types/annexes/to_sign (ContentCategory, to_sign=True)
        """
        at_folder = api.content.create(
            container=portal,
            id="annexes_types",
            title="Annexes Types",
            type="ContentCategoryConfiguration",
            exclude_from_nav=True,
        )
        category_group = api.content.create(
            type="ContentCategoryGroup",
            title="Annexes",
            container=at_folder,
            id="annexes",
        )
        icon_path = os.path.join(os.path.dirname(__file__), "tests", u"icône1.png")
        with open(icon_path, "rb") as fl:
            api.content.create(
                type="ContentCategory",
                title="To sign",
                container=category_group,
                icon=NamedBlobImage(fl.read(), filename=u"icône1.png"),
                id="to_sign",
                predefined_title="To be signed",
                to_sign=True,
                show_preview=False,
            )

    def _setup_shared_content(self, portal):
        """Pre-create folders and annexes shared across multiple test classes.

        Creates:
          portal/folder0/annex0,2,4,6,8,10  (annex1.pdf)
          portal/folder1/annex1,3,5,7,9,11  (annex2.pdf)
        """
        pdf_files = ["annex1.pdf", "annex2.pdf"]
        for f in range(2):
            api.content.create(container=portal, type="Folder", id="folder{}".format(f), title="Folder {}".format(f))
        for i in range(12):
            self._create_annex(
                portal,
                portal["folder{}".format(i % 2)],
                "annex{}".format(i),
                "Annex {}".format(i),
                "0123456000000{:02d}".format(i),
                pdf_filename=pdf_files[i % 2],
            )

    def _create_annex(self, portal, container, annex_id, title, scan_id, pdf_filename="annex1.pdf"):
        tests_dir = os.path.join(os.path.dirname(__file__), "tests")
        category_id = calculate_category_id(portal["annexes_types"]["annexes"]["to_sign"])
        with open(os.path.join(tests_dir, pdf_filename), "rb") as f:
            return api.content.create(
                container=container,
                type="annex",
                id=annex_id,
                title=title,
                content_category=category_id,
                scan_id=scan_id,
                file=NamedBlobFile(
                    data=f.read(),
                    filename=u"{}.pdf".format(annex_id),
                    contentType="application/pdf",
                ),
            )


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
