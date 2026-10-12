# -*- coding: utf-8 -*-
"""config tests for this package."""
from imio.esign.config import get_esign_registry_signers_order
from imio.esign.config import set_esign_registry_signers_order
from imio.esign.config import update_esign_registry_signers_order
from imio.esign.tests.base import BaseEsignTest
from plone.registry.interfaces import IRegistry
from zope.component import getUtility


class TestConfig(BaseEsignTest):

    def test_update_esign_registry_signers_order(self):
        """update_esign_registry_signers_order: drops removed signers, never adds new ones."""
        # new signers are not ordered: they sign last
        self.register_signers("user1", "user2", "user3")
        update_esign_registry_signers_order()
        self.assertEqual(get_esign_registry_signers_order(), ())
        # saved order kept, removed signer dropped, new signer not added
        set_esign_registry_signers_order(["user3", "user1"])
        self.register_signers("user1", "user2", "user4")
        update_esign_registry_signers_order()
        self.assertEqual(get_esign_registry_signers_order(), ["user1"])
        # a signer coming back is not ordered anymore
        self.register_signers("user1", "user2", "user3", "user4")
        update_esign_registry_signers_order()
        self.assertEqual(get_esign_registry_signers_order(), ["user1"])
        # record not installed yet: nothing to do
        del getUtility(IRegistry).records["imio.esign.signers_order"]
        update_esign_registry_signers_order()
        self.assertEqual(get_esign_registry_signers_order(default=None), None)
