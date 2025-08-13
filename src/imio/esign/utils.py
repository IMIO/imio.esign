# -*- coding: utf-8 -*-
from datetime import datetime
from imio.esign import E_SIGN_ROOT_URL
from imio.helpers.content import uuidsToObjects
from imio.helpers.content import uuidToObject
from persistent.list import PersistentList
from persistent.mapping import PersistentMapping
from plone import api
from plone.api.validation import mutually_exclusive_parameters
from zope.annotation import IAnnotations

import json
import logging
import requests


logger = logging.getLogger("imio.esign")
SESSION_URL = "imio/esign/v1/luxtrust/sessions"


def add_files_to_session(signers, files_uids=(), seal=False, session_id=None, title=None):
    """Add files to a session with the given signers.

    :param session_id:
    :param files_uids: files uids
    :param signers: a list of signers, each is a tuple with userid and email
    :param seal: seal or not
    :return: session_id
    """
    esign_dic = get_session_annotation()
    if session_id and session_id not in esign_dic:
        logger.error("Session with id %s not found in esign annotations.", session_id)
        session_id = session = None
    else:
        session_id, session = discriminate_sessions(signers, seal)
    if not session:
        session_id, session = create_session(signers=signers, seal=seal, title=title, annot=esign_dic)
    for uid in files_uids:
        annex = uuidToObject(uuid=uid, unrestricted=True)
        session["files"].append(
            {
                "scan_id": annex.scan_id,
                "filename": annex.file.filename or "no_filename",
                "title": annex.title or "no_title",
                "uid": uid,
            }
        )
        esign_dic["uids"][uid] = session_id
    session["last_update"] = datetime.now()


def create_external_session(
    session_id, endpoint_url, files_uids, signers, seal=None, acroform=True, b64_cred=None, esign_root_url=None
):
    """Create a session with the given signers and files.

    :param session_id: internal session id
    :param endpoint_url: the endpoint URL to communicate with
    :param files_uids: files uids in site
    :param signers: a list of signers emails
    :param seal: a seal code, if any
    :param acroform: whether to use sign places
    :param b64_cred: base64 encoded credentials for authentication
    :return: session information
    """
    session_url = get_esign_root_url(esign_root_url)
    files = get_files_from_uids(files_uids)
    data_payload = {
        "commonData": {
            "endpointUrl": endpoint_url,
            "documentData": [{"filename": filename, "uniqueCode": unique_code} for unique_code, filename, _ in files],
            "imioAppSessionId": session_id and session_id or 1,
        }
    }

    if signers:
        data_payload["signData"] = {"users": list(signers), "acroform": acroform}

    if seal:
        data_payload["sealData"] = {"sealCode": seal}

    files_payload = [("files", (filename, file_content)) for _, filename, file_content in files]

    # Headers avec autorisation
    headers = {"accept": "application/json"}
    if b64_cred:
        headers["Authorization"] = "Basic {}".format(b64_cred)

    logger.info(data_payload)
    ret = post_request(session_url, data={"data": json.dumps(data_payload)}, headers=headers, files=files_payload)
    logger.info("Response: %s", ret.text)
    return ret


def create_session(signers, seal, title=None, annot=None):
    """Create a session with the given signers and seal.

    :param signers: a list of signers, each is a tuple with userid and email
    :param seal: a seal code, if any
    :param title: title of the session
    :param annot: esign annotation, if not provided it will be fetched
    :return: session id and session information
    """
    if not annot:
        annot = get_session_annotation()
    sessions = annot.setdefault("sessions", PersistentMapping())
    session_id = annot["numbering"]
    annot["numbering"] += 1

    sessions[session_id] = {
        "signers": PersistentList([{"userid": userid, "email": email, "status": ""} for userid, email in signers]),
        "seal": seal,
        "title": title,
        "state": "draft",
        "last_update": datetime.now(),
        "files": PersistentList(),
    }
    return session_id, sessions[session_id]


def discriminate_sessions(signers, seal, annot=None):
    """Discriminate sessions based on seal value and signers in the same order.

    :param signers: a list of signers, each is a tuple with userid and email
    :param seal: a seal code, if any
    :param annot: esign annotation, if not provided it will be fetched
    :return: session id and session if found, or (None, None) if no session found
    """
    if not annot:
        annot = get_session_annotation()
    sessions = annot.get("sessions", {})

    for session_id, session in sessions.items():
        if session.get("seal") != seal:
            continue
        session_signers = session.get("signers", [])
        if len(signers) != len(session_signers):
            continue

        signers_match = all(
            (userid, email) == (s["userid"], s["email"]) for (userid, email), s in zip(signers, session_signers)
        )
        if signers_match:
            return session_id, session

    return None, None


def get_esign_root_url(esign_root_url):
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
        annotations["imio.esign"] = PersistentMapping({"numbering": 0, "sessions": PersistentMapping(),
                                                       "uids": PersistentMapping()})
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
