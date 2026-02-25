# -*- coding: utf-8 -*-
from datetime import datetime
from datetime import timedelta
from imio.esign import _tr as _
from imio.esign import API_ROOT_URL
from imio.esign import logger
from imio.esign.config import get_registry_file_url
from imio.esign.config import get_registry_max_session_size
from imio.esign.config import get_registry_seal_code
from imio.esign.config import get_registry_seal_email
from imio.esign.config import get_registry_sign_code
from imio.esign.config import get_registry_vat_number
from imio.esign.interfaces import IContextUidProvider
from imio.helpers.content import uuidToObject
from imio.helpers.transmogrifier import get_correct_id
from imio.helpers.ws import get_auth_token
# from imio.pyutils.system import post_request
from imio.pyutils.utils import shortuid_encode_id
from os import path
from persistent.list import PersistentList
from persistent.mapping import PersistentMapping
from plone import api
from zope.annotation import IAnnotations
from zope.component import getAdapter

import json
import requests


SESSION_URL = "imio/esign/v1/luxtrust/sessions"


def get_filesize(uid):
    """Get the file size of an annex.

    :param uid: The UID of the annex.
    :return: The file size in bytes, or 0 if not found.
    """
    annex = uuidToObject(uuid=uid, unrestricted=True)
    if not annex:
        logger.error("Annex with UID %s not found.", uid)
        return 0
    return getattr(annex.__parent__, "categorized_elements", {}).get(uid, {}).get("filesize", annex.file.size)


def add_files_to_session(
    signers, files_uids, seal=None, acroform=True, session_id=None, title="", discriminators=(), watchers=(),
    create_session_custom_data=None
):
    """Add files to a session with the given signers.

    :param signers: a list of signers, each is a quartet with userid, email, fullname and position text
    :param files_uids: files uids list
    :param seal: seal or not
    :param acroform: boolean to indicate if signer tag is in files
    :param session_id: session number
    :param title: optional string for session title. If it contains {sign_id} or {session_id} it will be replaced
    :param discriminators: optional list of string discriminators to use for session discrimination
    :param watchers: optional list of external esign session watchers emails (used only when creating a new session)
    :param create_session_custom_data: optional custom dict of custom session data
    :return: session_id, session
    """
    annot = get_session_annotation()
    size = sum(get_filesize(uid) for uid in files_uids)
    if session_id is not None:
        if session_id not in annot["sessions"]:
            logger.error("Session with id %s not found in esign annotations.", session_id)
            session_id = session = None
        else:
            session = annot["sessions"][session_id]
    else:
        session_id, session = discriminate_sessions(signers, seal, acroform, discriminators=discriminators, size=size)
    if not session:
        session_id, session = create_session(
            signers, seal, acroform=acroform, title=title, annot=annot, discriminators=discriminators,
            watchers=watchers,
            create_session_custom_data=create_session_custom_data,
        )
    session["size"] = session.get("size", 0) + size
    existing_files = [path.splitext(f["filename"])[0] for f in session["files"]]
    for uid in files_uids:
        annex = uuidToObject(uuid=uid, unrestricted=True)
        context_uid_provider = getAdapter(annex, IContextUidProvider)
        context_uid = context_uid_provider.get_context_uid()
        filename, ext = path.splitext(annex.file.filename or "no_filename.pdf")
        new_filename = get_correct_id(existing_files, filename)
        session["files"].append(
            {
                "scan_id": annex.scan_id,
                "filename": new_filename + ext,
                "title": annex.title or "no_title",
                "uid": uid,
                "context_uid": context_uid,
                "status": "",
            }
        )
        existing_files.append(new_filename)
        annot["uids"][uid] = session_id
        annot["c_uids"].setdefault(context_uid, PersistentList()).append(uid)
    if session["client_id"] is None:
        # FIXME what if scan_id is None ?
        session["client_id"] = session["files"][0]["scan_id"][0:7]
        session["sign_id"] = "{}{:05d}".format(session["client_id"], session_id)
        if u"{sign_id}" in session["title"]:
            session["title"] = session["title"].replace(u"{sign_id}", session["sign_id"])
        if u"{session_id}" in session["title"]:
            session["title"] = session["title"].replace(u"{session_id}", str(session_id))
    session["last_update"] = datetime.now()
    annot._p_changed = True
    return session_id, session


def create_external_session(session_id, esign_root_url=None):
    """Create a session with the given signers and files.

    :param session_id: internal session id
    :param esign_root_url: the root URL for the e-sign service, if not provided it will use the default API_ROOT_URL
    :return: session information
    """
    session_url = get_esign_session_url(esign_root_url)
    annot = get_session_annotation()
    session = annot["sessions"].get(session_id)
    if not session:
        logger.error("Session with id %s not found.", session_id)
        return "_session_not_found_"
    files = []
    for file_dic in session["files"]:
        uid = file_dic["uid"]
        annex = uuidToObject(uuid=uid, unrestricted=True)
        if not annex:
            logger.error("Annex with UID %s not found.", uid)
            continue
        files.append((file_dic["scan_id"], file_dic["filename"], annex.file.data, uid))
    if not files:
        logger.error("No files found for session %s.", session_id)
        return "_no_files_"
    portal = api.portal.get()  # noqa F841
    if not session["title"]:
        session["title"] = _("Session ${id}", mapping={"id": session_id})
    data_payload = {
        "commonData": {
            "endpointUrl": portal.absolute_url() + "/@external_session_feedback",
            "documentData": [{"filename": filename, "uniqueCode": "{}__{}".format(unique_code, uid),
                              "docUuid": get_suid_from_uuid(uid)}
                             for unique_code, filename, z, uid in files],
            "imioAppSessionId": session["sign_id"],
            "sessionName": session["title"],
        }
    }
    # not mandatory now
    vat_number = get_registry_vat_number(default="BE0000000097")
    data_payload["commonData"]["vatNumber"] = vat_number

    signers = [fdic["email"] for fdic in session["signers"]]
    if signers:
        data_payload["signData"] = {
            "users": list(signers),
            "acroform": session["acroform"],
        }
        sign_code = get_registry_sign_code()
        if sign_code:
            data_payload["signData"]["signCode"] = sign_code
        if session.get("watchers", ()):
            data_payload["signData"]["watchers"] = list(session["watchers"])

    if session["seal"]:
        seal_email = get_registry_seal_email()
        if not seal_email:
            logger.error("No seal email configured in registry.")
            return "_no_seal_email_"
        seal_code = get_registry_seal_code()  # PADES_SEAL
        if not seal_code:
            logger.error("No seal code configured in registry.")
            return "_no_seal_code_"
        data_payload["sealData"] = {
            "users": seal_email and [seal_email] or [],
            # "placeholderName": "SCEAU",  # default
            "acroform": bool(seal_email),  # default False
            "watchers": list(session.get("watchers", [])),
            "sealCode": seal_code,
        }

    # files_payload = {filename: file_content for z, filename, file_content, uid in files}
    files_payload = [("files", (filename, file_content)) for z, filename, file_content, uid in files]

    # Headers avec autorisation
    headers = {
        "accept": "application/json",
        "Authorization": "Bearer %s" % get_auth_token(),
    }

    logger.info(data_payload)
    # for future use when pyutils > 1.2.1
    # ret = post_request(
    #     session_url,
    #     headers=headers,
    #     data={"data": json.dumps(data_payload, default=vars)},
    #     files=files_payload,
    #     timeout=10,
    # )
    ret = requests.post(
        session_url,
        headers=headers,
        data={"data": json.dumps(data_payload, default=vars)},
        files=files_payload,
        timeout=10,
    )
    if ret.status_code == 200:
        session["state"] = "sent"
    logger.info("Response: %s", ret.text)
    # {"message":"Request received in the expected format. Session is being created in background."}
    return ret


def create_session(signers, seal=False, acroform=True, title=None, annot=None, discriminators=(), watchers=(),
                   create_session_custom_data=None):
    """Create a session with the given signers and seal.

    :param signers: a list of signers, each is a quartet with userid, email, fullname and position text
    :param seal: seal boolean
    :param acroform: acroform boolean
    :param title: title of the session
    :param annot: esign annotation, if not provided it will be fetched
    :param discriminators: optional list of string discriminators
    :param watchers: optional list of external esign session watchers emails
    :param create_session_custom_data: optional custom dict of custom session data
    :return: session id and session information
    """
    if not annot:
        annot = get_session_annotation()
    sessions = annot.setdefault("sessions", PersistentMapping())
    session_id = annot["numbering"]
    annot["numbering"] += 1

    sessions[session_id] = PersistentMapping({
        "acroform": acroform,
        "client_id": None,
        "discriminators": discriminators,
        "files": PersistentList(),
        "last_update": datetime.now(),
        "seal": seal,
        "sign_id": None,
        "sign_url": None,
        "signers": PersistentList(
            [
                {"userid": userid, "email": email, "fullname": fullname, "position": position, "status": ""}
                for userid, email, fullname, position in signers
            ]
        ),
        "watchers": PersistentList(watchers),
        "state": "draft",
        "title": title,
        "returns": PersistentList(),
    })
    if create_session_custom_data:
        for k, v in create_session_custom_data.items():
            sessions[session_id][k] = v
    return session_id, sessions[session_id]


def discriminate_sessions(signers, seal, acroform, discriminators=(), annot=None, size=0):
    """Discriminate sessions based on seal value and signers in the same order.

    :param signers: a list of signers, each is a tuple with userid and email
    :param seal: seal boolean
    :param acroform: boolean value indicating if acroform is used
    :param discriminators: optional list of string discriminators
    :param size: size in bytes of the files to be added to the session
    :param annot: esign annotation, if not provided it will be fetched
    :return: session id and session if found, or (None, None) if no session found
    """
    if not annot:
        annot = get_session_annotation()
    sessions = annot.get("sessions", {})
    max_session_size = get_registry_max_session_size() * 1024**2

    for session_id, session in sessions.items():
        if session["state"] != "draft":
            continue
        if session.get("seal") != seal:
            continue
        if session.get("acroform") != acroform:
            continue
        session_signers = session.get("signers", [])
        if len(signers) != len(session_signers):
            continue
        if size + session.get("size", 0) > max_session_size:
            continue

        if set(discriminators) != set(session.get("discriminators", ())):
            continue

        signers_match = all(
            (userid, email) == (s["userid"], s["email"]) for (userid, email, z, z), s in zip(signers, session_signers)
        )
        if signers_match:
            return session_id, session

    return None, None


def get_esign_session_url(esign_root_url):
    """Get the e-sign root URL."""
    if esign_root_url:
        return "{}/{}".format(esign_root_url, SESSION_URL)
    else:
        return "{}/{}".format(API_ROOT_URL, SESSION_URL)


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


def get_session_info(session_id, portal=None):
    """Return a session info for a given numbering.

    :param session_id: the session id to return
    :param portal: portal if necessary to get the session annotation
    """
    annot = get_session_annotation(portal=portal)
    if session_id in annot['sessions']:
        return annot['sessions'][session_id]


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
        session["size"] = max(0, session.get("size", 0) - get_filesize(uid))
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


def get_file_download_url(uid, root_url=None, short_uid=None):
    """Get the file download URL for a given file UID.

    :param uid: file UID
    :param root_url: root URL. If not provided, the settings value is used
    :param short_uid: take this short UID instead of computing it
    :return: file download URL, short_uid
    """
    if not root_url:
        root_url = get_registry_file_url()

    if not root_url:
        raise Exception("No root URL provided for file download url.")
    if not short_uid:
        short_uid = get_suid_from_uuid(uid)
    return "{}/{}".format(root_url.strip('/'), short_uid), short_uid


def get_max_download_date(obj, delta=timedelta(days=90), adate=None):
    """Get the maximum download date for e-sign files. Is takes the modification date and adds delta.

    :param obj: content object
    :param delta: timedelta to add to modification date
    :param adate: use date instead of modification date
    :return: maximum download date
    """
    if adate is None:
        adate = obj.modified().asdatetime().date()
    return adate + delta


def get_suid_from_uuid(uid):
    """Get the short UID from a given UUID.

    :param uid: UUID
    :return: short UID
    """
    return shortuid_encode_id(uid, separator="-", block_size=5)


def get_state_description(state):
    """
    Get a human readable description for a given session state.

                       ┌─────────┐
                       │  draft  │
                       └────┬────┘
                            │
                 (session sent to Paraphéo)
                            │
                            ▼
                       ┌─────────┐
             ┌─────────│  sent   │─────────┐
             │         └────┬────┘         │
             │              │              │
    (error occurred)     (ready)   (signer refused)
             │              │              │
             ▼              ▼              ▼
        ┌─────────┐    ┌─────────┐    ┌─────────┐
        │ errored │    │ to_sign │    │ refused │
        └─────────┘    └────┬────┘    └─────────┘
                            │
                   (documents signed)
                            │
                            ├──────────────┐
                            │              │
            (sent back successfully)  (send back failed)
                            │              │
                            ▼              │
                      ┌──────────┐         │
                      │ returned │         │
                      └─────┬────┘         │
                            │              │
                 (documents received)      │
                            │              │
                            ▼              ▼
                      ┌───────────┐   ┌─────────┐
                      │ finalized │   │ signed  │
                      └───────────┘   └─────────┘
    """
    return {
        'draft': u'The session is getting ready to be sent to Paraphéo by a signing manager.',
        'sent': u'The session has been sent to Paraphéo.',
        'errored': u'The session encountered an error during its processing.',
        'to_sign': u'The session is ready to be signed in Paraphéo.',
        'signed': u'The session is finished but signed documents couldn\'t be sent back to the application.',
        'refused': u'The session has been cancelled because a signer refused a document.',
        'returned': u'The session is finished and signed documents are on the way back to the application.',
        'finalized': u'The session is finished and signed documents have been sent back to the application.',
    }.get(state, "")
