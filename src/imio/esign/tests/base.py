# -*- coding: utf-8 -*-
"""Shared base test class for imio.esign tests."""
from imio.esign.testing import IMIO_ESIGN_INTEGRATION_TESTING
from io import BytesIO
from mock import patch
from plone.app.testing import login
from plone.app.testing import setRoles
from plone.app.testing import TEST_USER_ID
from plone.app.testing import TEST_USER_NAME
from plone.namedfile.file import NamedBlobFile
from reportlab.pdfgen import canvas
from zope.component import getGlobalSiteManager
from zope.schema.interfaces import IVocabularyFactory
from zope.schema.vocabulary import SimpleTerm
from zope.schema.vocabulary import SimpleVocabulary

import os
import unittest
import zipfile


TESTS_DIR = os.path.dirname(__file__)
ODT_CONTENT_TYPE = "application/vnd.oasis.opendocument.text"


def tag(nb):
    """Return the acroform signature tag of the given signer number."""
    return u'{{#"ID":"Signer%d","Size":{"Height":"70","Width":"200"}#}}' % nb


def seal_tag():
    """Return the acroform seal tag."""
    return u'{{#"ID":"SCEAU","Size":{"Height":"200","Width":"200"}#}}'


def pdf_file(*paragraphs):
    """Return a NamedBlobFile holding a one page pdf with the given lines of text."""
    buf = BytesIO()
    pdf = canvas.Canvas(buf)
    y = 800
    for paragraph in paragraphs:
        pdf.drawString(30, y, paragraph)
        y -= 30
    pdf.save()
    return NamedBlobFile(data=buf.getvalue(), filename=u"file.pdf", contentType="application/pdf")


def odt_file(*paragraphs):
    """Return a NamedBlobFile holding an odt whose content.xml has the given paragraphs."""
    body = u"".join([u"<text:p>" + paragraph + u"</text:p>" for paragraph in paragraphs])
    xml = (
        u"<?xml version='1.0' encoding='UTF-8'?><office:document-content>"
        u"<office:body><office:text>" + body + u"</office:text></office:body></office:document-content>"
    )
    buf = BytesIO()
    zip_file = zipfile.ZipFile(buf, "w")
    zip_file.writestr("content.xml", xml.encode("utf-8"))
    zip_file.close()
    return NamedBlobFile(data=buf.getvalue(), filename=u"file.odt", contentType=ODT_CONTENT_TYPE)


class FakePerson(object):
    def __init__(self, userid):
        self.userid = userid


class FakeHeldPosition(object):
    """Fake held position, the signers order holds held position UIDs."""

    def __init__(self, userid):
        self.person = FakePerson(userid)

    def get_person(self):
        return self.person


class BaseEsignTest(unittest.TestCase):
    """Base class: shared layer, minimal setUp, and optionnal helpers."""

    layer = IMIO_ESIGN_INTEGRATION_TESTING

    def setUp(self):
        self.portal = self.layer["portal"]
        self.request = self.layer["request"]
        self.request.form.clear()
        setRoles(self.portal, TEST_USER_ID, ["Manager"])
        login(self.portal, TEST_USER_NAME)

    def register_signers(self, *userids):
        """Make the given userids the signers listed by the imio.esign.signers vocabulary."""
        vocab = SimpleVocabulary([SimpleTerm(uid, uid, uid.upper()) for uid in userids])
        gsm = getGlobalSiteManager()  # not persisted, unlike the site manager, so a lambda can be registered
        name = "imio.esign.signers"
        self.addCleanup(gsm.registerUtility, gsm.getUtility(IVocabularyFactory, name), IVocabularyFactory, name)
        gsm.registerUtility(lambda context: vocab, IVocabularyFactory, name)

    def fake_signers_held_positions(self, userids_by_id=None):
        """Resolve the signers order ids to fake held positions, no contacts being available.
        Each id is mapped to its person userid by p_userids_by_id, unknown ids are not found.
        When not given, each id is its own person userid, so userids may be used as order ids."""
        if userids_by_id is None:
            def resolve(uid, **kwargs):
                return FakeHeldPosition(uid)
        else:
            def resolve(uid, **kwargs):
                return FakeHeldPosition(userids_by_id[uid]) if uid in userids_by_id else None
        patcher = patch("imio.esign.adapters.uuidToObject", side_effect=resolve)
        patcher.start()
        self.addCleanup(patcher.stop)
