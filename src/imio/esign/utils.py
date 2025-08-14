# -*- coding: utf-8 -*-
from datetime import datetime
from imio.esign import E_SIGN_ROOT_URL
from imio.esign.interfaces import IContextUidProvider
from imio.helpers.content import uuidsToObjects
from imio.helpers.content import uuidToObject
from persistent.list import PersistentList
from persistent.mapping import PersistentMapping
from plone import api
from plone.api.validation import mutually_exclusive_parameters
from zope.annotation import IAnnotations
from zope.component import getAdapter

import json
import logging
import requests


logger = logging.getLogger("imio.esign")
SESSION_URL = "imio/esign/v1/luxtrust/sessions"


def add_files_to_session(signers, files_uids, seal=None, acroform=True, session_id=None, title=None, discriminators=()):
    """Add files to a session with the given signers.

    :param signers: a list of signers, each is a tuple with userid and email
    :param files_uids: files uids list
    :param seal: seal or not
    :param acroform: boolean to indicate if signer tag is in files
    :param session_id: session number
    :param title: optional string
    :param discriminators: optional list of string discriminators to use for session discrimination
    :return: session_id, session
    """
    # TODO
    # signers: add fullname, position
    annot = get_session_annotation()
    if session_id is not None:
        if session_id not in annot["sessions"]:
            logger.error("Session with id %s not found in esign annotations.", session_id)
            session_id = session = None
        else:
            session = annot["sessions"][session_id]
    else:
        session_id, session = discriminate_sessions(signers, seal, acroform, discriminators=discriminators)
    if not session:
        session_id, session = create_session(
            signers, seal, acroform=acroform, title=title, annot=annot, discriminators=discriminators
        )
    for uid in files_uids:
        annex = uuidToObject(uuid=uid, unrestricted=True)
        context_uid_provider = getAdapter(annex, IContextUidProvider)
        context_uid = context_uid_provider.get_context_uid()
        session["files"].append(
            {
                "scan_id": annex.scan_id,
                "filename": annex.file.filename or "no_filename",
                "title": annex.title or "no_title",
                "uid": uid,
                "context_uid": context_uid,
            }
        )
        annot["uids"][uid] = session_id
        annot["c_uids"].setdefault(context_uid, PersistentList()).append(uid)
    if session["client_id"] is None:
        session["client_id"] = session["files"][0]["scan_id"][:7]
    session["last_update"] = datetime.now()
    return session_id, session


def create_external_session(session_id, endpoint_url, b64_cred=None, esign_root_url=None):
    """Create a session with the given signers and files.

    :param session_id: internal session id
    :param endpoint_url: the endpoint URL to communicate with
    :param b64_cred: base64 encoded credentials for authentication
    :param esign_root_url: the root URL for the e-sign service, if not provided it will use the default E_SIGN_ROOT_URL
    :return: session information
    """
    session_url = get_esign_session_url(esign_root_url)
    annot = get_session_annotation()
    session = annot["sessions"].get(session_id)
    if not session:
        logger.error("Session with id %s not found.", session_id)
        return None
    files_uids = [fdic["uid"] for fdic in session["files"]]
    files = get_files_from_uids(files_uids)
    app_session_id = "{}{:05d}".format(session["client_id"], session_id)
    data_payload = {
        "commonData": {
            "endpointUrl": endpoint_url,
            "documentData": [{"filename": filename, "uniqueCode": unique_code} for unique_code, filename, _ in files],
            "imioAppSessionId": app_session_id,
        }
    }

    signers = [fdic["email"] for fdic in session["signers"]]
    data_payload["signData"] = {"users": list(signers), "acroform": session["acroform"]}

    if session["seal"] is not None:
        data_payload["sealData"] = {"sealCode": session["seal"]}

    files_payload = [("files", (filename, file_content)) for _, filename, file_content in files]

    # Headers avec autorisation
    headers = {"accept": "application/json"}
    if b64_cred:
        headers["Authorization"] = "Basic {}".format(b64_cred)

    logger.info(data_payload)
    ret = post_request(session_url, data={"data": json.dumps(data_payload)}, headers=headers, files=files_payload)
    logger.info("Response: %s", ret.text)
    return ret


def create_session(signers, seal, acroform=True, title=None, annot=None, discriminators=()):
    """Create a session with the given signers and seal.

    :param signers: a list of signers, each is a tuple with userid and email
    :param seal: a seal code, if any
    :param acroform: acroform boolean
    :param title: title of the session
    :param annot: esign annotation, if not provided it will be fetched
    :param discriminators: optional list of string discriminators
    :return: session id and session information
    """
    if not annot:
        annot = get_session_annotation()
    sessions = annot.setdefault("sessions", PersistentMapping())
    session_id = annot["numbering"]
    annot["numbering"] += 1

    sessions[session_id] = {
        "acroform": acroform,
        "client_id": None,
        "discriminators": discriminators,
        "files": PersistentList(),
        "last_update": datetime.now(),
        "seal": seal,
        "signers": PersistentList([{"userid": userid, "email": email, "status": ""} for userid, email in signers]),
        "state": "draft",
        "title": title,
    }
    return session_id, sessions[session_id]


def discriminate_sessions(signers, seal, acroform, discriminators=(), annot=None):
    """Discriminate sessions based on seal value and signers in the same order.

    :param signers: a list of signers, each is a tuple with userid and email
    :param seal: a seal code, if any
    :param acroform: boolean value indicating if acroform is used
    :param discriminators: optional list of string discriminators
    :param annot: esign annotation, if not provided it will be fetched
    :return: session id and session if found, or (None, None) if no session found
    """
    if not annot:
        annot = get_session_annotation()
    sessions = annot.get("sessions", {})

    for session_id, session in sessions.items():
        if session.get("seal") != seal:
            continue
        if session.get("acroform") != acroform:
            continue
        session_signers = session.get("signers", [])
        if len(signers) != len(session_signers):
            continue

        if set(discriminators) != set(session.get("discriminators", ())):
            continue

        signers_match = all(
            (userid, email) == (s["userid"], s["email"]) for (userid, email), s in zip(signers, session_signers)
        )
        if signers_match:
            return session_id, session

    return None, None


def get_esign_session_url(esign_root_url):
    """Get the e-sign root URL."""
    if esign_root_url:
        return "{}/{}".format(esign_root_url, SESSION_URL)
    else:
        return "{}/{}".format(E_SIGN_ROOT_URL, SESSION_URL)


def get_files_from_uids(uids):
    """Get files from uids.

    :param uids: uids
    :return: list of triplets (scan_id, filename, file_content) for each coresponding object
    """
    annexes = uuidsToObjects(uuids=uids, unrestricted=True)

    files_data = []
    for annex in annexes:
        if not hasattr(annex, "scan_id") or not annex.scan_id:
            logger.error("Annex %s has no scan_id", annex.absolute_url())
            continue
        else:
            scan_id = annex.scan_id
        if not hasattr(annex, "file") or not annex.file:
            logger.error("Annex %s has no file", annex.absolute_url())
            continue
        else:
            filename = annex.file.filename or "no_filename"
            file_content = annex.file.data

        files_data.append((scan_id, filename, file_content))

    return files_data


def get_session_annotation(portal=None):
    """Get the e-sign session annotation."""
    if not portal:
        portal = api.portal.get()
    annotations = IAnnotations(portal)
    if "imio.esign" not in annotations:
        annotations["imio.esign"] = PersistentMapping(
            {
                "numbering": 0,
                "sessions": PersistentMapping(),
                "uids": PersistentMapping(),
                "c_uids": PersistentMapping(),
            }
        )
    return annotations["imio.esign"]


@mutually_exclusive_parameters("json", "files")
def post_request(url, data=None, json=None, headers=None, files=None):
    """Post data to url.

    :param url: the url to post to
    :param data: a data struct to consider
    :param json: a json serializable object
    :param headers: headers to use
    :param files: files to upload (dict or list of tuples)
    """
    kwargs = {}

    if files:
        kwargs["files"] = files
        if headers:
            # Exclude Content-Type with multipart/form-data
            kwargs["headers"] = {k: v for k, v in headers.items() if k.lower() != "content-type"}
    if "headers" not in kwargs:
        kwargs["headers"] = headers or (
            {"Content-Type": "application/json"} if json else {"Content-Type": "application/x-www-form-urlencoded"}
        )
    if json:
        kwargs["json"] = json
    else:
        kwargs["data"] = data

    with requests.post(url, **kwargs) as response:
        if response.status_code != 200:
            # if files:
            # del kwargs["files"]  # remove files from kwargs to avoid sending them in the log
            kwargs["files"] = [(tup[0], (tup[1][0], len(tup[1][1]))) for tup in kwargs["files"]]
            logger.error("Error while posting data '%s' to '%s': %s" % (kwargs, url, response.text))
        return response


def remove_context_from_session(context_uids):
    """Remove all files from a session that are linked to the given context UIDs.

    :param context_uids: context_uids list
    """
    annot = get_session_annotation()
    c_uids = annot["c_uids"]
    for context_uid in context_uids:
        if context_uid not in c_uids:
            logger.error("Context UID %s not found in session", context_uid)
            continue
        remove_files_from_session(list(c_uids[context_uid]))


def remove_files_from_session(files_uids):
    """Remove files from their corresponding sessions.

    :param files_uids: list of file UIDs to remove
    """
    annot = get_session_annotation()
    sessions = annot["sessions"]
    uids = annot["uids"]
    c_uids = annot["c_uids"]

    for uid in files_uids:
        session_id = uids.get(uid)
        if session_id is None:
            logger.error("No session found for file UID %s", uid)
            continue
        del uids[uid]
        if session_id not in sessions:
            logger.error("Session %s not found", session_id)
            continue
        session = sessions[session_id]
        i = 0
        context_uid = None
        for j, dic in enumerate(session["files"]):
            if dic["uid"] == uid:
                i = j
                context_uid = dic["context_uid"]
                break
        else:
            logger.error("File UID %s not found in session %s", uid, session_id)
            continue

        del session["files"][i]
        if not session["files"]:
            del sessions[session_id]
        else:
            session["last_update"] = datetime.now()

        if context_uid in c_uids and uid in c_uids[context_uid]:
            c_uids[context_uid].remove(uid)
            if not c_uids[context_uid]:
                del c_uids[context_uid]

        # logger.info("File UID %s removed from session %s", uid, session_id)


def remove_session(session_id):
    """Remove a complete session and all its associated files.

    :param session_id: ID of the session to remove
    """
    annot = get_session_annotation()
    sessions = annot["sessions"]
    uids = annot["uids"]
    c_uids = annot["c_uids"]

    if session_id not in sessions:
        logger.error("Session %s not found", session_id)
        return

    session = sessions[session_id]
    for fdic in session["files"]:
        if fdic["uid"] in uids:
            del uids[fdic["uid"]]
        if fdic["context_uid"] in c_uids and fdic["uid"] in c_uids[fdic["context_uid"]]:
            c_uids[fdic["context_uid"]].remove(fdic["uid"])
            if not c_uids[fdic["context_uid"]]:
                del c_uids[fdic["context_uid"]]

    del sessions[session_id]
    # logger.info("Session %s removed", session_id)
