# -*- coding: utf-8 -*-
"""table tests for this package."""
from imio.esign.browser.table import FilteredSessionsTable
from imio.esign.browser.table import SealColumn
from imio.esign.config import set_esign_registry_seal_code
from imio.esign.config import set_esign_registry_seal_email
from imio.esign.tests.base import BaseEsignTest
from imio.esign.utils import create_session
from plone import api


class TestFilteredSessionsTable(BaseEsignTest):
    """Tests for FilteredSessionsTable."""

    def setUp(self):
        super(TestFilteredSessionsTable, self).setUp()
        api.user.create(email="user1@sign.com", username="user1", password="password1")  # noqa: S106
        self.signers = [("user1", "user1@sign.com", "User 1", "Position 1")]
        self.folder = self.portal["folder0"]
        self.mock_view = type("MockView", (), {})()

    def test_filter_session(self):
        """Returns True only for sessions with state 'draft'."""
        table = FilteredSessionsTable(self.folder, self.mock_view, self.request)
        self.assertTrue(table.filter_session({"state": "draft"}))
        self.assertFalse(table.filter_session({"state": "sent"}))
        self.assertFalse(table.filter_session({"state": "finalized"}))
        self.assertFalse(table.filter_session({}))

    def test_values(self):
        """Loads from annotation filtered to draft and reverse-sorted otherwise."""
        # --- empty annotation: returns empty list ---
        table = FilteredSessionsTable(self.folder, self.mock_view, self.request)
        self.assertEqual(table.values, [])

        # --- from annotation: filters to draft, reverse-sorted by id ---
        sid_a, _session = create_session(self.signers)
        sid_b, session_b = create_session(self.signers)
        table = FilteredSessionsTable(self.folder, self.mock_view, self.request)
        values = table.values
        self.assertEqual(len(values), 2)
        self.assertEqual(values[0]["id"], sid_b)
        self.assertEqual(values[1]["id"], sid_a)

        # --- non-draft sessions are excluded ---
        session_b["state"] = "sent"
        table = FilteredSessionsTable(self.folder, self.mock_view, self.request)
        values = table.values
        self.assertEqual(len(values), 1)
        self.assertEqual(values[0]["id"], sid_a)

    def test_setUpColumns(self):
        """Returns 5 columns without seal; 6 with seal config set."""
        table = FilteredSessionsTable(self.folder, self.mock_view, self.request)
        columns = table.setUpColumns()
        self.assertEqual(len(columns), 5)
        self.assertFalse(any(isinstance(column, SealColumn) for column in columns))

        self.addCleanup(set_esign_registry_seal_code, u"")
        self.addCleanup(set_esign_registry_seal_email, u"")
        set_esign_registry_seal_code(u"PADES_SEAL")
        set_esign_registry_seal_email(u"seal@example.com")
        columns = table.setUpColumns()
        self.assertEqual(len(columns), 6)
        self.assertTrue(any(isinstance(column, SealColumn) for column in columns))

    def test_update(self):
        """Populates rows from draft sessions; empty when none exist."""
        # --- no draft sessions → empty rows ---
        table = FilteredSessionsTable(self.folder, self.mock_view, self.request)
        table.update()
        self.assertEqual(len(table.rows), 0)

        # --- with a draft session → one row ---
        create_session(self.signers)
        table = FilteredSessionsTable(self.folder, self.mock_view, self.request)
        table.update()
        self.assertEqual(len(table.rows), 1)
