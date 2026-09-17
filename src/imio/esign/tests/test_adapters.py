# -*- coding: utf-8 -*-

from imio.esign.adapters import DefaultContextUidProvider
from imio.esign.adapters import ISignable
from imio.esign.adapters import SignableAdapter
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


class TestSignableAdapter(BaseEsignTest):

    def test_get_filename(self):
        annex = self.portal["folder0"]["annex0"]
        adapter = getAdapter(annex.aq_parent, ISignable)
        self.assertIsInstance(adapter, SignableAdapter)
        self.assertEqual(adapter.get_filename(annex), u"annex0.pdf")
        # a name already used in the session gets a numbered suffix
        self.assertEqual(adapter.get_filename(annex, existing_files=["annex0"]), u"annex0-1.pdf")
        self.assertEqual(adapter.get_filename(annex, existing_files=["annex0", "annex0-1"]), u"annex0-2.pdf")
        # a __<uid> suffix is kept: imio.zamqp parses it back
        annex.file.filename = u"Rapport__{}.pdf".format(annex.UID())
        self.assertEqual(adapter.get_filename(annex), u"Rapport__{}.pdf".format(annex.UID()))
        # and it survives deduplication, the suffix landing after the uid
        self.assertEqual(
            adapter.get_filename(annex, existing_files=["Rapport__{}".format(annex.UID())]),
            u"Rapport__{}-1.pdf".format(annex.UID()),
        )
        annex.file.filename = None
        self.assertEqual(adapter.get_filename(annex), u"no_filename.pdf")
