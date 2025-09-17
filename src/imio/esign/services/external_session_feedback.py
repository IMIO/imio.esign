# -*- coding: utf-8 -*-
from datetime import datetime
from imio.esign.utils import get_session_annotation
from plone.restapi.deserializer import json_body
from plone.restapi.services import Service


class ExternalSessionFeedbackPost(Service):
    def reply(self):
        """Handle the external session feedback.

        Needs json body with:
            * "app_session_id": "123456", app_session_id
            * "code": "some_code", feedback identification code
            * "session_state": "to_create_session"; session state
            * "value": like sign URL or signer email
            * "message": "some message", optional message with feedback
        """
        if not self.authorized():
            self.request.response.setStatus(403)
            return {"message": "Unauthorized access"}
        data = json_body(self.request)
        app_session_id = data.get("app_session_id")
        if not app_session_id:
            self.request.response.setStatus(400)
            return {"message": "app_session_id is required"}
        code = data.get("code")
        if not code:
            self.request.response.setStatus(400)
            return {"message": "code is required"}
        value = data.get("value")
        try:
            annot = get_session_annotation()
            session_id = int(app_session_id[7:])
            if session_id not in annot["sessions"]:
                self.request.response.setStatus(400)
                return {"message": "Session ID {} not found".format(session_id)}
            session = annot["sessions"][session_id]
            session_update = {"returns": session["returns"]}
            session_update["returns"].append((code, data.get("message", ""), datetime.now()))
            if code == "21":
                session_update["state"] = "to_sign"
                if value:
                    session_update["sign_url"] = value
            elif code == "22":
                signer_idx = [i for i, d in enumerate(session["signers"]) if d["email"] == value][0]
                session_update["signers"][signer_idx]["state"] = "signed"
            elif code == "23":
                session_update["state"] = "returned"
            elif code == "52":
                session_update["state"] = "refused"
                signer_idx = [i for i, d in enumerate(session["signers"]) if d["email"] == value][0]
                session_update["signers"][signer_idx]["state"] = "refused"
            elif code == "53":
                session_update["state"] = "signed"
            elif code in ("50", "40", "51", "41"):
                session_update["state"] = "errored"
            session_state = data.get("session_state")
            if session_state and session_state != session["state"]:
                session_update["state"] = session_state
            if session_update:
                session.update(session_update)
                session["last_update"] = datetime.now()

        except Exception as e:
            self.request.response.setStatus(500)
            return {"message": str(e)}
        return {"message": "Information correctly handled"}

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
