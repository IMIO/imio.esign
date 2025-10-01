# -*- coding: utf-8 -*-
from datetime import datetime
from imio.esign.utils import get_session_annotation
from plone.restapi.deserializer import json_body
from plone.restapi.services import Service

import json
import logging


logger = logging.getLogger("imio.esign")


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
        if not self.authorized():
            self.request.response.setStatus(403)
            return {"message": "Unauthorized access"}
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
        if value:
            value = json.loads(value)
        db_state = data.get("session_state")
        try:
            annot = get_session_annotation()
            session_id = int(app_session_id[7:])
            if session_id not in annot["sessions"]:
                self.request.response.setStatus(400)
                return {"message": "Session ID {} not found".format(session_id)}
            session = annot["sessions"][session_id]
            session_update = {"returns": session["returns"]}
            session_update["returns"].append((code, db_state, data.get("value", ""), data.get("message", ""),
                                              datetime.now()))
            if code == 21:
                # sign_session_confirmed
                session_update["state"] = "to_sign"
                if value and "sign_session_url" in value and not session["sign_url"]:
                    session_update["sign_url"] = value["sign_session_url"]
            elif code == 22:
                # one_signer_accepted
                if value and "signed_user_emails" in value:
                    for i, d in enumerate(session["signers"]):
                        if d["state"] in ("signed", "refused"):
                            continue
                        if d["email"] in value["signed_user_emails"]:
                            session_update["signers"][i]["state"] = "signed"
            elif code == 23:
                # upload_success (files returned)
                session_update["state"] = "returned"
            elif code == 52:
                # one_signer_refused
                session_update["state"] = "refused"
                if value and "refused_user_email" in value:
                    signer_idx = [i for i, d in enumerate(session["signers"]) if d["refused_user_email"] == value][0]
                    session_update["signers"][signer_idx]["state"] = "refused"
            elif code == 53:
                # upload_failed
                session_update["state"] = "signed"
            elif code in (50, 40, 51, 41):
                # seal_creation_error, seal_creation_not_available, sign_creation_error, sign_creation_not_available
                session_update["state"] = "errored"
            if session_update:
                session.update(session_update)
                session["last_update"] = datetime.now()

        except Exception as e:
            self.request.response.setStatus(500)
            return {"message": str(e)}
        return {"message": "Information correctly handled"}
    """ microservice session state
    to_create_session = "to_create_session"
    session_creation_failed = "session_creation_failed"
    to_sign = "to_sign"
    refused = "refused"
    to_upload = "to_upload"
    to_notify_ged_upload = "to_notify_ged_upload"
    completed = "completed"
    """

    def authorized(self):
        """Check if the user is authorized to access this service."""
        return True


"""
State:
to_create_session
to_sign
to_upload
refused
"""
