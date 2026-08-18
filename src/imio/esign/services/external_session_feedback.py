# -*- coding: utf-8 -*-
from datetime import datetime
from imio.esign import logger
from imio.esign.audit import audit
from imio.esign.utils import get_session_annotation
from imio.helpers.ws import verify_auth_token
from plone.restapi.deserializer import json_body
from plone.restapi.services import Service
from zExceptions import Unauthorized


class ExternalSessionFeedbackPost(Service):
    def reply(self):  # noqa C901
        """Handle the external session feedback.

        Needs json body with:
            * "app_session_id": int 1234560001, app_session_id
            * "code": int some_code, feedback identification code
            * "session_state": microservice session state
            * "value": json dict contaaining sign URL or signer/refused emails
            * "message": "some message", optional message with feedback
        """
        data = json_body(self.request)
        app_session_id = data.get("app_session_id")
        logger.info("External session feedback received: {}".format(data))
        if not app_session_id:
            self.request.response.setStatus(400)
            return {"message": "app_session_id is required"}
        code = int(data.get("code"))
        if not code:
            self.request.response.setStatus(400)
            return {"message": "code is required"}
        value = data.get("value") or {}
        db_state = data.get("session_state")
        try:
            annot = get_session_annotation()
            session_id = int(app_session_id[7:])
            if session_id not in annot["sessions"]:
                self.request.response.setStatus(400)
                return {"message": "Session ID {} not found".format(session_id)}
            session = annot["sessions"][session_id]
            session_update = {"returns": session["returns"]}
            session_update["returns"].append(
                (code, db_state, data.get("value", ""), data.get("message", ""), datetime.now())
            )
            if code == 21:
                # 21: sign_session_confirmed
                session_update["state"] = "to_sign"
                if value and "sign_session_url" in value and not session["sign_url"]:
                    session_update["sign_url"] = value["sign_session_url"]
            elif code == 22:
                # 22: signature_signed (one signer signed)
                if value and "signed_users" in value:
                    session_update["signers"] = session["signers"]
                    for i, d in enumerate(session["signers"]):
                        if d["status"] in ("signed", "refused"):
                            continue
                        if d["email"] in value["signed_users"]:
                            session_update["signers"][i]["status"] = "signed"
            elif code == 52:
                # 52: document_declined (one signer refused)
                session_update["state"] = "refused"
                if value and "user" in value:
                    session_update["signers"] = session["signers"]
                    for i, d in enumerate(session["signers"]):
                        if d["email"] == value["user"]:
                            session_update["signers"][i]["status"] = "refused"
                            break
            elif code == 23:
                # 23: upload_successful (files returned)
                session_update["state"] = "returned"
                session_update["signers"] = session["signers"]
                for i, d in enumerate(session["signers"]):
                    if d["status"] not in ("signed", "refused"):
                        session_update["signers"][i]["status"] = "signed"
            elif code == 53:
                # 53: upload_error
                session_update["state"] = "signed"
            elif code in (50, 51, 54, 55, 56, 57, 58, 59):
                # 50: seal_creation_error
                # 51: sign_creation_error
                # 54: fatal_error_session_creation
                # 55: error_event_notification_signature
                # 56: error_event_notification_refusal
                # 57: fatal_error_completion_notification
                # 58: fatal_error_unknown_notification
                # 59: fatal_error_unknown
                session_update["state"] = "errored"
            elif code == 60:
                # 60: session deleted
                if session["state"] in ("sent", "to_sign"):
                    session_update["state"] = "errored"
                session_update["sign_url"] = ""
            if session_update:
                session.update(session_update)
                session["last_update"] = datetime.now()
            audit(
                "session_feedback",
                'session={} code={} db_state={} data="{}"'.format(session_id, code, db_state, data),
            )

        except Exception as e:
            self.request.response.setStatus(500)
            logger.error(str(e))
            return {"message": str(e)}
        return {"message": "Information correctly handled"}

    def _authorized(self):
        """Check if the user is authorized to access this service."""
        auth_header = getattr(self.request, "_auth", None)
        if not auth_header or not auth_header.startswith("Bearer "):
            return False
        token = auth_header[7:]  # len("Bearer ") == 7
        if not token:
            return False
        return verify_auth_token(token, groups=["access_imio-apps-docs"])

    def check_permission(self):
        """Override the default permission check to implement token-based authentication."""
        if not self._authorized():
            raise Unauthorized("Unauthorized: Invalid or missing authentication token")
