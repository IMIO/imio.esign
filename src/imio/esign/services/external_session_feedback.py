# -*- coding: utf-8 -*-
from datetime import datetime
from imio.esign.utils import get_session_annotation
from plone.restapi.deserializer import json_body
from plone.restapi.services import Service


class ExternalSessionFeedbackPost(Service):
    def reply(self):
        """Handle the external session feedback.

        Needs json body with:
            * "session_id": "123456", app_session_id
            * "code": "some_code", feedback identification code
            * "session_state": "to_create_session"; session state
            * "sign_url": "http://example.com/sign", sign URL
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
        try:
            annot = get_session_annotation()
            session_id = int(app_session_id[7:])
            if session_id not in annot["sessions"]:
                self.request.response.setStatus(400)
                return {"message": "Session ID {} not found".format(session_id)}
            session = annot["sessions"][session_id]
            session_update = {}
            session_state = data.get("session_state")
            if session_state:
                session_update["state"] = session_state
            sign_url = data.get("sign_url")
            if sign_url:
                session_update["sign_url"] = sign_url
            if session_update:
                session.update(session_update)
                session["last_update"] = datetime.now()
        except Exception as e:
            self.request.response.setStatus(500)
            return {"message": str(e)}
        return {"success": True, "message": "Information correctly handled"}

    def authorized(self):
        """Check if the user is authorized to access this service."""
        return True


"""
Events
{
    6: "SIGNATURE_SIGNED",
    7: "DOCUMENT_DECLINED",
    8: "DOCUMENT_REINSTATE",
    10: "STEP_DECLINED",
    18: "STEP_COMMENT_ADDED",
    24: "STEP_SUSPENDED",
    25: "STEP_RESUMED",
    26: "STEP_CANCELED",
}
State:
to_create_session
to_sign
to_upload
refused
"""
