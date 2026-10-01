# -*- coding: utf-8 -*-
"""Shared base test class for imio.esign tests."""
from imio.esign.testing import IMIO_ESIGN_INTEGRATION_TESTING
from io import BytesIO
from plone.app.testing import login
from plone.app.testing import setRoles
from plone.app.testing import TEST_USER_ID
from plone.app.testing import TEST_USER_NAME
from plone.namedfile.file import NamedBlobFile
from reportlab.pdfgen import canvas

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


class BaseEsignTest(unittest.TestCase):
    """Base class: shared layer, minimal setUp, and optionnal helpers."""

    layer = IMIO_ESIGN_INTEGRATION_TESTING

    def setUp(self):
        self.portal = self.layer["portal"]
        self.request = self.layer["request"]
        self.request.form.clear()
        setRoles(self.portal, TEST_USER_ID, ["Manager"])
        login(self.portal, TEST_USER_NAME)
