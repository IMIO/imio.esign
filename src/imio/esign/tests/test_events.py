# -*- coding: utf-8 -*-
"""events tests for this package."""
from collective.iconifiedcategory.utils import calculate_category_id
from imio.esign.events import on_annex_added
from imio.esign.tests.base import BaseEsignTest
from imio.esign.tests.base import pdf_file
from imio.esign.tests.base import seal_tag
from imio.esign.tests.base import tag
from plone import api
from Products.statusmessages.interfaces import IStatusMessage
from zope.annotation.interfaces import IAnnotations


class TestEvents(BaseEsignTest):
    """Tests for the events module."""

    def _add_annex(self, annex_id, file_object):
        """Create an annex holding the given file in folder0."""
        return api.content.create(
            container=self.portal["folder0"],
            type="annex",
            id=annex_id,
            title=u"Tagged annex",
            content_category=calculate_category_id(self.portal["annexes_types"]["annexes"]["to_sign"]),
            scan_id="0123456000009{}".format(len(self.portal["folder0"])),
            file=file_object,
        )

    def test_on_annex_added(self):
        """The acroform tags of a new annex are listed, and nothing is shown without a tag."""
        # --- a file holding no tag says nothing ---
        self._add_annex("annex-no-tag", pdf_file(u"no tag here"))
        self.assertEqual(IStatusMessage(self.request).show(), [])

        # --- signature and seal tags, in document order, duplicates listed every time ---
        self._add_annex("annex-tags", pdf_file(tag(2), tag(1), seal_tag(), seal_tag()))
        messages = IStatusMessage(self.request).show()
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0].type, "info")
        self.assertIn(u"Tagged annex", messages[0].message)
        self.assertIn(u"Signer2, Signer1, SCEAU, SCEAU", messages[0].message)

        # --- Signer0 is never announced: no signer can fill it ---
        self._add_annex("annex-signer0", pdf_file(tag(0)))
        self.assertEqual(IStatusMessage(self.request).show(), [])
        self._add_annex("annex-signer0-and-1", pdf_file(tag(0), tag(1)))
        messages = IStatusMessage(self.request).show()
        self.assertEqual(len(messages), 1)
        self.assertNotIn(u"Signer0", messages[0].message)
        self.assertIn(u"Signer1", messages[0].message)

    def test_on_annex_added_generated_file(self):
        """A file produced from a template says nothing: its tags come from the template."""
        # --- while the generation view is publishing, before it writes its annotation ---
        class _FakeView(object):
            __name__ = "persistent-document-generation"

        self.request["PUBLISHED"] = _FakeView()
        self._add_annex("annex-generated", pdf_file(tag(1), seal_tag()))
        self.assertEqual(IStatusMessage(self.request).show(), [])
        del self.request.other["PUBLISHED"]

        # --- later, on a file that already carries the generation annotation ---
        annex = self._add_annex("annex-annotated", pdf_file(tag(1)))
        IStatusMessage(self.request).show()  # consume the message of the creation above
        IAnnotations(annex)["documentgenerator"] = {"template_uid": "some-uid"}
        on_annex_added(annex, None)
        self.assertEqual(IStatusMessage(self.request).show(), [])
