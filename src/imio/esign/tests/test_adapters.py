# -*- coding: utf-8 -*-

from imio.esign.adapters import DefaultContextUidProvider
from imio.esign.interfaces import IContextUidProvider
from imio.esign.interfaces import IItemOrderProvider
from imio.esign.tests.base import BaseEsignTest
from plone import api
from zope.component import getAdapter


class TestDefaultContextUidProvider(BaseEsignTest):

    def test_get_context_uid(self):
        annex = self.portal["folder0"]["annex0"]
        provider = getAdapter(annex, IContextUidProvider)
        self.assertEqual(provider.get_context_uid(), self.portal["folder0"].UID())

        class Dummy(object):
            pass

        provider = DefaultContextUidProvider(Dummy())
        self.assertIsNone(provider.get_context_uid())


class TestDefaultItemOrderProvider(BaseEsignTest):

    def test_get_item_order(self):
        folder = self.portal["folder0"]
        provider = getAdapter(folder, IItemOrderProvider)
        order = provider.get_item_order()
        children = list(folder.values())
        for idx, child in enumerate(children):
            self.assertEqual(order[child.UID()], idx)

        empty = api.content.create(container=self.portal, type="Folder", id="empty-folder")
        provider = getAdapter(empty, IItemOrderProvider)
        self.assertEqual(provider.get_item_order(), {})
