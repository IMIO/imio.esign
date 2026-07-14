# -*- coding: utf-8 -*-
"""Services tests for this package."""
from imio.esign.services.external_session_feedback import ExternalSessionFeedbackPost
from imio.esign.tests.base import BaseEsignTest
from imio.esign.utils import add_files_to_session
from mock import patch

import json


class TestExternalSessionFeedbackPost(BaseEsignTest):
    """Tests for ExternalSessionFeedbackPost."""

    def setUp(self):
        super(TestExternalSessionFeedbackPost, self).setUp()
        self.request.other.pop("BODY", None)
        self.signers = [("user1", "user1@sign.com", "User 1", "Position 1")]
        self.annex = self.portal["folder0"]["annex0"]
        self.session_id, self.session = add_files_to_session(self.signers, [self.annex.UID()])[-1]
        self.sign_id = self.session["sign_id"]
        self.request._auth = "Bearer test-token"

    def _make_service(self):
        """Instantiate ExternalSessionFeedbackPost without the adapter mechanism."""
        service = ExternalSessionFeedbackPost.__new__(ExternalSessionFeedbackPost)
        service.context = self.portal
        service.request = self.request
        return service

    def _reply(self, data):
        """Call reply() with mocked verify_auth_token; inject body via request.other."""
        self.request.set("BODY", json.dumps(data))
        with patch(
            "imio.esign.services.external_session_feedback.verify_auth_token", return_value=True
        ):  # real Keycloak OAuth endpoint — no local server
            return self._make_service().reply()

    def test_authorized(self):
        """_authorized() returns False without valid Bearer token; True with verified token."""
        service = self._make_service()

        # no _auth attribute
        del self.request._auth
        self.assertFalse(service._authorized())

        # non-Bearer prefix
        self.request._auth = "Basic dXNlcjpwYXNz"
        self.assertFalse(service._authorized())

        # Bearer with empty token
        self.request._auth = "Bearer "
        self.assertFalse(service._authorized())

        # valid format, verify_auth_token returns False
        self.request._auth = "Bearer test-token"
        with patch("imio.esign.services.external_session_feedback.verify_auth_token", return_value=False):
            self.assertFalse(service._authorized())

        # valid format, verify_auth_token returns True
        with patch("imio.esign.services.external_session_feedback.verify_auth_token", return_value=True):
            self.assertTrue(service._authorized())

    def test_reply(self):
        """reply() validates auth/input, processes all feedback codes, updates session state."""
        annex1 = self.portal["folder0"]["annex2"]

        # missing app_session_id
        result = self._reply({"code": 21})
        self.assertEqual(self.request.response.getStatus(), 400)
        self.assertIn("app_session_id", result["message"])
        self.request.response.setStatus(200)

        # session not found
        result = self._reply({"app_session_id": "012345699999", "code": 21})
        self.assertEqual(self.request.response.getStatus(), 400)
        self.assertIn("not found", result["message"])
        self.request.response.setStatus(200)

        # code 21: state updated, sign_url set, returns appended
        result = self._reply(
            {
                "app_session_id": self.sign_id,
                "code": 21,
                "session_state": "to_sign",
                "value": {"sign_session_url": "https://sign.example.com/session/1"},
                "message": "Session confirmed",
            }
        )
        self.assertEqual(result, {"message": "Information correctly handled"})
        self.assertEqual(self.session["state"], "to_sign")
        self.assertEqual(self.session["sign_url"], "https://sign.example.com/session/1")
        self.assertEqual(self.session["returns"][0][0], 21)

        # code 21: existing sign_url not overwritten
        self._reply(
            {
                "app_session_id": self.sign_id,
                "code": 21,
                "value": {"sign_session_url": "https://new.example.com/"},
            }
        )
        self.assertEqual(self.session["sign_url"], "https://sign.example.com/session/1")

        # code 22: matching signer email → status 'signed'
        _, s22 = add_files_to_session(self.signers, [annex1.UID()], discriminators=("c22",))[-1]
        self._reply(
            {
                "app_session_id": s22["sign_id"],
                "code": 22,
                "value": {"signed_users": ["user1@sign.com"]},
            }
        )
        self.assertEqual(s22["signers"][0]["status"], "signed")

        # code 22: signer already 'refused' is not updated
        _, s22b = add_files_to_session(self.signers, [annex1.UID()], discriminators=("c22b",))[-1]
        s22b["signers"][0]["status"] = "refused"
        self._reply(
            {
                "app_session_id": s22b["sign_id"],
                "code": 22,
                "value": {"signed_users": ["user1@sign.com"]},
            }
        )
        self.assertEqual(s22b["signers"][0]["status"], "refused")

        # code 23: state → 'returned'
        _, s23 = add_files_to_session(self.signers, [annex1.UID()], discriminators=("c23",))[-1]
        self._reply({"app_session_id": s23["sign_id"], "code": 23})
        self.assertEqual(s23["state"], "returned")

        # code 52: state → 'refused'; matching signer → 'refused'
        _, s52 = add_files_to_session(self.signers, [annex1.UID()], discriminators=("c52",))[-1]
        self._reply(
            {
                "app_session_id": s52["sign_id"],
                "code": 52,
                "value": {"user": "user1@sign.com"},
            }
        )
        self.assertEqual(s52["state"], "refused")
        self.assertEqual(s52["signers"][0]["status"], "refused")

        # code 53: state → 'signed' (documents signed but not returned)
        _, s53 = add_files_to_session(self.signers, [annex1.UID()], discriminators=("c53",))[-1]
        self._reply({"app_session_id": s53["sign_id"], "code": 53})
        self.assertEqual(s53["state"], "signed")

        # error codes: state → 'errored'
        for code in (50, 51, 54, 55, 56, 57, 58, 59):
            _, serr = add_files_to_session(self.signers, [annex1.UID()], discriminators=(str(code),))[-1]
            self._reply({"app_session_id": serr["sign_id"], "code": code})
            self.assertEqual(serr["state"], "errored")

        # returns: entry structure (code, db_state, value, message, datetime)
        _, srtn = add_files_to_session(self.signers, [annex1.UID()], discriminators=("rtn",))[-1]
        self._reply(
            {
                "app_session_id": srtn["sign_id"],
                "code": 23,
                "session_state": "completed",
                "value": {"info": "ok"},
                "message": "All done",
            }
        )
        entry = srtn["returns"][0]
        self.assertEqual(entry[0], 23)
        self.assertEqual(entry[1], "completed")
        self.assertEqual(entry[2], {"info": "ok"})
        self.assertEqual(entry[3], "All done")
