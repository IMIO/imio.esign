# -*- coding: utf-8 -*-

from imio.esign.browser.table import SignersColumn
from imio.esign.config import set_esign_registry_enforce_signers_order
from imio.esign.tests.base import BaseEsignTest


class TestSignersColumn(BaseEsignTest):

    def test_header(self):
        """When the signers order is enforced, the header specifies the signing order
        and a help icon explains it may differ from the order on the document."""
        column = SignersColumn(self.portal, self.request, None)
        self.assertEqual(column.header, u"Signers")
        self.assertEqual(column.renderHeadCell(), u"Signers")
        set_esign_registry_enforce_signers_order(True)
        self.assertEqual(column.header, u"Signers (signing order)")
        self.assertEqual(
            column.renderHeadCell(),
            u"Signers (signing order) <span class='far fa-question-circle' "
            u"title='Signers are listed in the enforced signing order, "
            u"it may be different from the order of the signers on the document.'></span>")
