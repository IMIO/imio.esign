# -*- coding: utf-8 -*-
"""acroform tests for this package."""
from collections import OrderedDict
from imio.esign.acroform import check_file
from imio.esign.acroform import extract_text
from imio.esign.acroform import format_errors
from imio.esign.acroform import get_session_acroform_errors
from imio.esign.acroform import get_tag_ids
from imio.esign.acroform import validate_seal_count
from imio.esign.acroform import validate_signer_numbers
from imio.esign.tests.base import BaseEsignTest
from imio.esign.tests.base import ODT_CONTENT_TYPE
from imio.esign.tests.base import odt_file
from imio.esign.tests.base import pdf_file
from imio.esign.tests.base import seal_tag
from imio.esign.tests.base import tag
from imio.esign.tests.base import TESTS_DIR
from imio.esign.utils import add_files_to_session
from plone.namedfile.file import NamedBlobFile

import os


class TestAcroform(BaseEsignTest):
    """Tests for the acroform module."""

    def setUp(self):
        super(TestAcroform, self).setUp()
        self.folder = self.portal["folder0"]
        self.annex = self.folder["annex0"]
        self.signers = [
            ("user1", "user1@sign.com", "User 1", "Position 1"),
            ("user2", "user2@sign.com", "User 2", "Position 2"),
        ]

    def test_extract_text(self):
        """pdf and odt are read, whitespace is dropped, unreadable files give u""."""
        # --- pdf ---
        self.assertEqual(extract_text(pdf_file(u"hello world")), u"helloworld")
        self.assertEqual(extract_text(pdf_file(tag(1), u"text")), u'{{#"ID":"Signer1","Size":{"Height":"70","Width":"200"}#}}text')

        # --- odt ---
        self.assertEqual(extract_text(odt_file(u"hello world")), u"helloworld")
        self.assertEqual(extract_text(odt_file(tag(2))), u'{{#"ID":"Signer2","Size":{"Height":"70","Width":"200"}#}}')

        # --- the quotes stored as xml entities, as appy/POD writes them ---
        escaped = odt_file(tag(1).replace(u'"', u"&quot;"), u"l&apos;essai")
        self.assertEqual(extract_text(escaped), u'{{#"ID":"Signer1","Size":{"Height":"70","Width":"200"}#}}l\'essai')
        self.assertEqual(get_tag_ids(escaped), ([1], 0))

        # --- a real pdf produced by LibreOffice: its embedded fonts defeat PyPDF2 ---
        with open(os.path.join(TESTS_DIR, "signer_tags.pdf"), "rb") as fh:
            real_pdf = NamedBlobFile(data=fh.read(), filename=u"signer_tags.pdf", contentType="application/pdf")
        self.assertIn(tag(1) + tag(2), extract_text(real_pdf))
        self.assertEqual(get_tag_ids(real_pdf), ([1, 2], 0))

        # --- unreadable: no file, no data, unsupported type, corrupt data ---
        self.assertEqual(extract_text(None), u"")
        self.assertEqual(extract_text(NamedBlobFile(data="", filename=u"f.pdf", contentType="application/pdf")), u"")
        self.assertEqual(
            extract_text(NamedBlobFile(data="plain text", filename=u"f.txt", contentType="text/plain")), u""
        )
        self.assertEqual(
            extract_text(NamedBlobFile(data="not a pdf", filename=u"f.pdf", contentType="application/pdf")), u""
        )
        self.assertEqual(extract_text(NamedBlobFile(data="not a zip", filename=u"f.odt",
                                                    contentType=ODT_CONTENT_TYPE)), u"")

    def test_get_tag_ids(self):
        """Signer numbers come in document order, seal tags are counted, unknown ids are ignored."""
        self.assertEqual(get_tag_ids(pdf_file(u"no tag here")), ([], 0))
        self.assertEqual(get_tag_ids(pdf_file(tag(2), tag(1))), ([2, 1], 0))
        self.assertEqual(get_tag_ids(odt_file(tag(1), tag(1))), ([1, 1], 0))

        # --- the seal tag, alone, beside a signer and twice ---
        self.assertEqual(get_tag_ids(odt_file(seal_tag())), ([], 1))
        self.assertEqual(get_tag_ids(pdf_file(tag(1), seal_tag())), ([1], 1))
        self.assertEqual(get_tag_ids(odt_file(seal_tag(), seal_tag())), ([], 2))

        # --- an id that is neither a signer nor the seal ---
        self.assertEqual(get_tag_ids(odt_file(u'{{#"ID":"WRONG"#}}')), ([], 0))

        # --- a padded number is not the signer number: the service would not fill it ---
        self.assertEqual(get_tag_ids(odt_file(u'{{#"ID":"Signer01"#}}')), ([], 0))
        self.assertEqual(get_tag_ids(odt_file(u'{{#"ID":"Signer10"#}}')), ([10], 0))

    def test_validate_signer_numbers(self):
        """No tag is valid; a complete set is valid; duplicate, unknown and missing are errors."""
        # --- no tag at all is always valid ---
        self.assertEqual(validate_signer_numbers([], 2), [])
        self.assertEqual(validate_signer_numbers([], 0), [])

        # --- one tag per signer, any order ---
        self.assertEqual(validate_signer_numbers([1, 2], 2), [])
        self.assertEqual(validate_signer_numbers([2, 1], 2), [])

        # --- the same signer twice ---
        errors = validate_signer_numbers([1, 1, 2], 2)
        self.assertEqual(len(errors), 1)
        self.assertIn(u"is present ${count} times", errors[0])
        self.assertEqual(errors[0].mapping, {"nb": 1, "count": 2})

        # --- a signer that does not exist ---
        errors = validate_signer_numbers([1, 2, 3], 2)
        self.assertEqual(len(errors), 1)
        self.assertIn(u"but ${count} signer(s) are defined", errors[0])
        self.assertEqual(errors[0].mapping, {"nb": 3, "count": 2})

        # --- an incomplete set ---
        errors = validate_signer_numbers([1], 2)
        self.assertEqual(len(errors), 1)
        self.assertIn(u"is missing", errors[0])
        self.assertEqual(errors[0].mapping, {"nb": 2})

        # --- a tag while no signer is defined ---
        errors = validate_signer_numbers([1], 0)
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].mapping, {"nb": 1, "count": 0})

    def test_validate_seal_count(self):
        """No seal tag is valid; one is valid with a seal; more than one and no seal are errors."""
        # --- no seal tag at all is always valid ---
        self.assertEqual(validate_seal_count(0, True), [])
        self.assertEqual(validate_seal_count(0, False), [])

        # --- exactly one tag while a seal is defined ---
        self.assertEqual(validate_seal_count(1, True), [])

        # --- the tag while no seal is defined ---
        errors = validate_seal_count(1, False)
        self.assertEqual(len(errors), 1)
        self.assertIn(u"no seal is defined", errors[0])

        # --- the tag several times ---
        errors = validate_seal_count(2, True)
        self.assertEqual(len(errors), 1)
        self.assertIn(u"is present ${count} times", errors[0])
        self.assertEqual(errors[0].mapping, {"count": 2})

        # --- several tags and no seal: only the missing seal is reported ---
        errors = validate_seal_count(2, False)
        self.assertEqual(len(errors), 1)
        self.assertIn(u"no seal is defined", errors[0])

    def test_check_file(self):
        """The errors of the file field of a content object."""
        self.annex.file = pdf_file(tag(1), tag(2))
        self.assertEqual(check_file(self.annex, 2), [])
        self.assertEqual(len(check_file(self.annex, 1)), 1)
        self.assertEqual(check_file(self.folder, 2), [])  # no file field at all

        # --- the signature tags are ignored when nb_signers is None ---
        self.assertEqual(check_file(self.annex, None), [])

        # --- the seal tag, with and without a seal on the container ---
        self.annex.file = pdf_file(tag(1), seal_tag())
        self.assertEqual(check_file(self.annex, 1, True), [])
        self.assertEqual(len(check_file(self.annex, 1, False)), 1)

        # --- a wrong signature tag and a wrong seal tag are both reported ---
        self.assertEqual(len(check_file(self.annex, 2, False)), 2)

    def test_get_session_acroform_errors(self):
        """Session files are checked against the number of signers of their session."""
        self.annex.file = pdf_file(tag(1))
        session_id, _session = add_files_to_session(self.signers, (self.annex.UID(),))[-1]

        # --- unknown session ---
        self.assertEqual(get_session_acroform_errors(9999), OrderedDict())

        # --- one tag but two signers: the missing one is reported ---
        errors = get_session_acroform_errors(session_id)
        self.assertEqual(list(errors.keys()), [self.annex.UID()])
        obj, context_uid, messages = errors[self.annex.UID()]
        self.assertEqual(obj, self.annex)
        self.assertEqual(context_uid, self.folder.UID())
        self.assertEqual(len(messages), 1)

        # --- a complete set of tags: nothing reported ---
        self.annex.file = pdf_file(tag(1), tag(2))
        self.assertEqual(get_session_acroform_errors(session_id), OrderedDict())

        # --- the seal tag is checked against the seal of the session ---
        self.annex.file = pdf_file(tag(1), tag(2), seal_tag())
        self.assertEqual(len(get_session_acroform_errors(session_id)), 1)  # this session has no seal
        sealed_id, _sealed = add_files_to_session(self.signers, (self.annex.UID(),), seal=True)[-1]
        self.assertEqual(get_session_acroform_errors(sealed_id), OrderedDict())
        self.annex.file = pdf_file(tag(1), tag(2), seal_tag(), seal_tag())
        self.assertEqual(len(get_session_acroform_errors(sealed_id)), 1)

    def test_format_errors(self):
        """The summary names each file and its messages."""
        messages = validate_signer_numbers([1], 2)
        summary = format_errors([(self.annex, messages)], self.request)
        self.assertTrue(summary.startswith(u"Annex 0: "))
        self.assertIn(u"Signer2", summary)
        self.assertEqual(format_errors([], self.request), u"")
