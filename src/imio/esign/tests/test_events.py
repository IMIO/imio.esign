# -*- coding: utf-8 -*-
"""events tests for this package."""
from collective.iconifiedcategory.event import IconifiedAttrChangedEvent
from collective.iconifiedcategory.utils import calculate_category_id
from imio.esign.acroform import get_tag_ids
from imio.esign.config import get_esign_registry_check_annexes_tags_outside_session
from imio.esign.config import set_esign_registry_check_annexes_tags_outside_session
from imio.esign.tests.base import BaseEsignTest
from imio.esign.tests.base import pdf_file
from imio.esign.tests.base import seal_tag
from imio.esign.tests.base import tag
from imio.esign.utils import add_files_to_session
from mock import patch
from plone import api
from Products.statusmessages.interfaces import IStatusMessage
from zope.annotation.interfaces import IAnnotations
from zope.event import notify
from zope.lifecycleevent import ObjectAddedEvent
from zope.lifecycleevent import ObjectModifiedEvent


class TestEvents(BaseEsignTest):
    """Tests for the events module."""

    def setUp(self):
        super(TestEvents, self).setUp()
        self.category_group = self.portal["annexes_types"]["annexes"]
        self.category = self.category_group["to_sign"]
        # to_sign/signed are only managed when signing is activated on the category group
        self.category_group.signed_activated = True

    def _add_annex(self, annex_id, file_object, **kwargs):
        """Create an annex holding the given file in folder0."""
        return api.content.create(
            container=self.portal["folder0"],
            type="annex",
            id=annex_id,
            title=u"Tagged annex",
            content_category=calculate_category_id(self.category),
            scan_id="0123456000009{}".format(len(self.portal["folder0"])),
            file=file_object,
            **kwargs
        )

    def test_on_annex_added(self):
        """The acroform tags of a new annex to sign (to_sign default value of its category)
        are listed, the malformed ones apart, nothing without a tag."""
        # --- a file holding no tag says nothing ---
        self._add_annex("annex-no-tag", pdf_file(u"no tag here"))
        self.assertEqual(IStatusMessage(self.request).show(), [])

        # --- signature and seal tags, in document order, duplicates listed every time ---
        annex = self._add_annex("annex-tags", pdf_file(tag(2), tag(1), seal_tag(), seal_tag()))
        self.assertTrue(annex.to_sign)
        messages = IStatusMessage(self.request).show()
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0].type, "info")
        self.assertIn(u"Tagged annex", messages[0].message)
        self.assertIn(u"Signer2, Signer1, SCEAU, SCEAU", messages[0].message)

        # --- a malformed tag is warned about apart: Signer0 cannot be filled by any signer ---
        self._add_annex("annex-signer0-and-1", pdf_file(tag(0), tag(1)))
        messages = IStatusMessage(self.request).show()
        self.assertEqual([message.type for message in messages], ["info", "warning"])
        self.assertNotIn(u"Signer0", messages[0].message)
        self.assertIn(u"Signer1", messages[0].message)
        self.assertIn(tag(0), messages[1].message)

    def test_on_annex_added_to_sign_given(self):
        """An annex created with to_sign=True: no IconifiedAttrChangedEvent is notified for to_sign,
        the tags are listed by on_annex_added, only once."""
        self.category.to_sign = False
        annex = self._add_annex("annex-to-sign", pdf_file(tag(1)), to_sign=True)
        self.assertTrue(annex.to_sign)
        messages = IStatusMessage(self.request).show()
        self.assertEqual(len(messages), 1)
        self.assertIn(u"Signer1", messages[0].message)

        # --- to_sign given but signing not activated: to_sign is set to False, nothing said ---
        self.category_group.signed_activated = False
        annex = self._add_annex("annex-not-activated", pdf_file(tag(1)), to_sign=True)
        self.assertFalse(annex.to_sign)
        self.assertEqual(IStatusMessage(self.request).show(), [])

    def test_tags_read_once_at_creation(self):
        """Whatever the way an annex to sign is created, its file is read only once.
        on_annex_added, on_annex_to_sign_changed and on_annex_modified are all
        notified at creation but only one of them reads the file."""

        def get_tag_ids_calls(create):
            with patch("imio.esign.acroform.get_tag_ids", side_effect=get_tag_ids) as mock_get_tag_ids:
                annex = create()
            self.assertTrue(annex.to_sign)
            IStatusMessage(self.request).show()
            return mock_get_tag_ids.call_count

        # --- to_sign default value of the category: on_annex_to_sign_changed ---
        self.assertEqual(get_tag_ids_calls(lambda: self._add_annex("annex-default", pdf_file(tag(1)))), 1)

        # --- to_sign given at creation (REST API, scripts, ...): on_annex_added ---
        self.category.to_sign = False
        self.assertEqual(
            get_tag_ids_calls(lambda: self._add_annex("annex-given", pdf_file(tag(1)), to_sign=True)), 1)
        self.category.to_sign = True

        # --- quickupload: created with deferred categorized events, modified when the file is set,
        # then added again once the content_category is set: on_annex_to_sign_changed ---
        def quickupload():
            self.request.set("defer_categorized_content_created_event", True)
            annex = api.content.create(
                container=self.portal["folder0"],
                type="annex",
                id="annex-quickupload",
                title=u"Tagged annex",
                scan_id="012345600000990",
                file=pdf_file(tag(1)),
            )
            notify(ObjectModifiedEvent(annex))
            self.request.set("defer_categorized_content_created_event", False)
            annex.content_category = calculate_category_id(self.category)
            notify(ObjectAddedEvent(annex))
            return annex

        self.assertEqual(get_tag_ids_calls(quickupload), 1)

    def test_check_annexes_tags_outside_session_disabled(self):
        """When the check_annexes_tags_outside_session setting is disabled, the file of an annex to sign
        that is not in a session is not read when it is added, set to sign or modified.
        Annexes in a session are still checked: tags displayed when modified."""
        self.assertTrue(get_esign_registry_check_annexes_tags_outside_session())
        set_esign_registry_check_annexes_tags_outside_session(False)
        with patch("imio.esign.acroform.get_tag_ids") as mock_get_tag_ids:
            # to_sign default value of the category
            annex = self._add_annex("annex-default", pdf_file(tag(1)))
            # to_sign given at creation
            self.category.to_sign = False
            self._add_annex("annex-given", pdf_file(tag(1)), to_sign=True)
            # set to sign
            other = self._add_annex("annex-other", pdf_file(tag(1)))
            notify(IconifiedAttrChangedEvent(other, "to_sign", {"to_sign": False}, {"to_sign": True}))
            # modified
            notify(ObjectModifiedEvent(annex))
        self.assertFalse(mock_get_tag_ids.called)
        self.assertEqual(IStatusMessage(self.request).show(), [])
        # the tags of an annex in a session are still displayed when it is modified
        add_files_to_session([("user1", "user1@sign.com", "User 1", "Position 1")], (annex.UID(),))
        notify(ObjectModifiedEvent(annex))
        messages = IStatusMessage(self.request).show()
        self.assertEqual(len(messages), 1)
        self.assertIn(u"Signer1", messages[0].message)

    def test_on_annex_added_not_to_sign(self):
        """The file of an annex that is not to sign is not read."""
        self.category.to_sign = False
        with patch("imio.esign.acroform.get_tag_ids") as mock_get_tag_ids:
            annex = self._add_annex("annex-not-to-sign", pdf_file(tag(1)))
        self.assertFalse(annex.to_sign)
        self.assertFalse(mock_get_tag_ids.called)
        self.assertEqual(IStatusMessage(self.request).show(), [])

        # --- nor when signing is not activated, even if to_sign by default in the category ---
        self.category.to_sign = True
        self.category_group.signed_activated = False
        with patch("imio.esign.acroform.get_tag_ids") as mock_get_tag_ids:
            annex = self._add_annex("annex-not-activated", pdf_file(tag(1)))
        self.assertFalse(annex.to_sign)
        self.assertFalse(mock_get_tag_ids.called)

    def test_on_annex_to_sign_changed(self):
        """The tags are listed when an existing annex becomes to sign, not otherwise."""
        self.category.to_sign = False
        annex = self._add_annex("annex-tags", pdf_file(tag(1)))
        self.assertEqual(IStatusMessage(self.request).show(), [])

        def changed(attr_name, old_values, new_values):
            notify(IconifiedAttrChangedEvent(annex, attr_name, old_values, new_values))
            return IStatusMessage(self.request).show()

        # --- becomes to sign ---
        messages = changed("to_sign", {"to_sign": False, "signed": False}, {"to_sign": True, "signed": False})
        self.assertEqual(len(messages), 1)
        self.assertIn(u"Signer1", messages[0].message)
        # --- already to sign (signed changed), set signed directly, no more to sign, another attribute: nothing said ---
        with patch("imio.esign.acroform.get_tag_ids") as mock_get_tag_ids:
            self.assertEqual(changed("to_sign", {"to_sign": True, "signed": False}, {"to_sign": True, "signed": True}), [])
            self.assertEqual(changed("to_sign", {"to_sign": False, "signed": False}, {"to_sign": True, "signed": True}), [])
            self.assertEqual(changed("to_sign", {"to_sign": True, "signed": False}, {"to_sign": False, "signed": False}), [])
            self.assertEqual(changed("to_print", {"to_print": False}, {"to_print": True}), [])
        self.assertFalse(mock_get_tag_ids.called)

    def test_on_annex_modified(self):
        """Any modification of an annex to sign (not signed yet) lists the tags of its file.
        The stored tags of a file are updated when it changed, even when it is not to sign
        or generated from a template, not once it is signed."""
        annex = self._add_annex("annex-tags", pdf_file(tag(1)))
        IStatusMessage(self.request).show()  # consume the message of the creation
        # --- file changed ---
        annex.file = pdf_file(tag(1), tag(2))
        notify(ObjectModifiedEvent(annex))
        messages = IStatusMessage(self.request).show()
        self.assertEqual(len(messages), 1)
        self.assertIn(u"Signer1, Signer2", messages[0].message)
        # --- only the title changed, the file is checked too ---
        annex.setTitle(u"New title")
        notify(ObjectModifiedEvent(annex))
        messages = IStatusMessage(self.request).show()
        self.assertEqual(len(messages), 1)
        self.assertIn(u"New title", messages[0].message)

        # --- signed or not to sign: nothing said, the unchanged file is not read again ---
        with patch("imio.esign.acroform.get_tag_ids") as mock_get_tag_ids:
            annex.signed = True
            notify(ObjectModifiedEvent(annex))
            annex.signed = False
            annex.to_sign = False
            notify(ObjectModifiedEvent(annex))
        self.assertFalse(mock_get_tag_ids.called)
        self.assertEqual(IStatusMessage(self.request).show(), [])

        def stored_signers(obj):
            return IAnnotations(obj)["imio.esign"]["acroform_tags"]["signers"]

        # --- not to sign: the stored tags are updated when the file changed ---
        annex.file = pdf_file(tag(2))
        notify(ObjectModifiedEvent(annex))
        self.assertEqual(stored_signers(annex), [2])
        self.assertEqual(IStatusMessage(self.request).show(), [])
        # --- generated from a template, edited to fix its tags: updated, nothing said ---
        annex.to_sign = True
        IAnnotations(annex)["documentgenerator"] = {"template_uid": "some-uid"}
        annex.file = pdf_file(tag(1))
        notify(ObjectModifiedEvent(annex))
        self.assertEqual(stored_signers(annex), [1])
        self.assertEqual(IStatusMessage(self.request).show(), [])
        # --- signed: not updated anymore ---
        annex.signed = True
        annex.file = pdf_file(tag(3))
        notify(ObjectModifiedEvent(annex))
        self.assertEqual(stored_signers(annex), [1])
        # --- nothing stored and not to sign: the file is not read ---
        self.category.to_sign = False
        other = self._add_annex("annex-other", pdf_file(tag(1)))
        notify(ObjectModifiedEvent(other))
        self.assertNotIn("imio.esign", IAnnotations(other))

    def test_on_annex_added_generated_file(self):
        """A file produced from a template says nothing: its tags come from the template."""
        # --- while the generation view is publishing, before it writes its annotation ---
        class _FakeView(object):
            __name__ = "persistent-document-generation"

        self.request["PUBLISHED"] = _FakeView()
        self._add_annex("annex-generated", pdf_file(tag(1), seal_tag()))
        self._add_annex("annex-generated-to-sign-given", pdf_file(tag(1), seal_tag()), to_sign=True)
        self.assertEqual(IStatusMessage(self.request).show(), [])
        del self.request.other["PUBLISHED"]

        # --- later, on a file that already carries the generation annotation ---
        annex = self._add_annex("annex-annotated", pdf_file(tag(1)))
        IStatusMessage(self.request).show()  # consume the message of the creation above
        IAnnotations(annex)["documentgenerator"] = {"template_uid": "some-uid"}
        notify(IconifiedAttrChangedEvent(annex, "to_sign", {"to_sign": False}, {"to_sign": True}))
        self.assertEqual(IStatusMessage(self.request).show(), [])

        # --- created with conv_from_uid (collective.documentgenerator convert_and_save_file),
        # it is set before the creation events so the file is not read, whatever the published view ---
        with patch("imio.esign.acroform.get_tag_ids") as mock_get_tag_ids:
            self._add_annex("annex-converted", pdf_file(tag(1)), conv_from_uid="some-uid")
            self._add_annex("annex-converted-to-sign-given", pdf_file(tag(1)), conv_from_uid="some-uid", to_sign=True)
        self.assertFalse(mock_get_tag_ids.called)
        self.assertEqual(IStatusMessage(self.request).show(), [])
        # conv_from_uid set to None (convert_and_save_file without from_uid) is not considered
        self._add_annex("annex-converted-no-uid", pdf_file(tag(1)), conv_from_uid=None)
        self.assertEqual(len(IStatusMessage(self.request).show()), 1)

    def test_on_categorized_annex_updated(self):
        """Renaming an annex keeps its session filename unique, without conflicting with itself."""
        signers = [("user1", "user1@sign.com", "User 1", "Position 1")]
        annex0 = self.portal["folder0"]["annex0"]
        annex2 = self.portal["folder0"]["annex2"]
        sid, session = add_files_to_session(signers, (annex0.UID(), annex2.UID()))[-1]
        self.assertEqual([f["filename"] for f in session["files"]], [u"annex0.pdf", u"annex2.pdf"])
        # renamed to a name already used in the session: deduplicated
        annex2.file.filename = u"annex0.pdf"
        notify(ObjectModifiedEvent(annex2))
        self.assertEqual([f["filename"] for f in session["files"]], [u"annex0.pdf", u"annex0-1.pdf"])
        # updated again: the generated name is the one it already has, it must not drift to annex0-2.pdf
        annex2.setTitle("New Annex 2")
        notify(ObjectModifiedEvent(annex2))
        self.assertEqual([f["filename"] for f in session["files"]], [u"annex0.pdf", u"annex0-1.pdf"])
        self.assertEqual(session["files"][1]["title"], "New Annex 2")
