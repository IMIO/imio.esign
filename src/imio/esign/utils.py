# -*- coding: utf-8 -*-

from collections import OrderedDict
from copy import deepcopy
from datetime import datetime
from datetime import timedelta
from imio.esign import _tr as _
from imio.esign import API_ROOT_URL
from imio.esign import logger
from imio.esign.audit import audit
from imio.esign.config import get_esign_registry_external_watchers
from imio.esign.config import get_esign_registry_file_url
from imio.esign.config import get_esign_registry_max_session_files
from imio.esign.config import get_esign_registry_max_session_size
from imio.esign.config import get_esign_registry_seal_code
from imio.esign.config import get_esign_registry_seal_email
from imio.esign.config import get_esign_registry_sign_code
from imio.esign.config import get_esign_registry_vat_number
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


def get_filesize(uid, session=None):
    """Get the file size of an annex.

    :param uid: The UID of the annex.
    :return: The file size in bytes, or 0 if not found.
    """
    parent = None
    annex = uuidToObject(uuid=uid, unrestricted=True)
    if not annex:
        # try to get context from session in case annex was not found
        # this can happen if we are in an event of a deleted annex
        if session is not None:
            for file_info in session['files']:
                if file_info['uid'] == uid:
                    parent = uuidToObject(uuid=file_info['context_uid'], unrestricted=True)
                    break
        if parent is None:
            logger.error("Annex with UID %s not found.", uid)
            return 0
    parent = parent or annex.__parent__
    return getattr(parent, "categorized_elements", {}).get(uid, {}).get("filesize", annex.file.size if annex else 0)


def add_files_to_session(  # noqa C901
    signers,
    files_uids,
    seal=None,
    acroform=True,
    session_id=None,
    title="",
    discriminators=(),
    watchers=(),
    create_session_custom_data=None,
):
    """Add files to a session with the given signers.

    Files are dispatched one by one. When the current target session would exceed
    ``max_session_size`` or ``max_session_files`` by adding the next file, it is
    marked as ``draft_full`` (so it will never be reused) and a new session is
    discriminated or created for the remaining files.

    :param signers: a list of signers, each is a quartet with userid, email, fullname and position text
    :param files_uids: files uids list
    :param seal: seal or not
    :param acroform: boolean to indicate if signer tag is in files
    :param session_id: explicit session number. When given, no dispatching is performed: all files
        go into this session even if it overflows the configured limits.
    :param title: optional string for session title. If it contains {sign_id} or {session_id} it will be replaced
    :param discriminators: optional list of string discriminators to use for session discrimination
    :param watchers: optional list of external esign session watchers emails (used only when creating a new session)
    :param create_session_custom_data: optional custom dict of custom session data
    :return: list of (session_id, session) tuples, one entry per distinct session used
    """
    annot = get_session_annotation()
    session = None
    if session_id is not None:
        if session_id not in annot["sessions"]:
            logger.error("Session with id %s not found in esign annotations.", session_id)
            session_id = None
        else:
            session = annot["sessions"][session_id]
    dispatch = session_id is None
    sessions_used = []

    for uid in files_uids:
        file_size = get_filesize(uid)

        if dispatch:
            session_id, session = discriminate_sessions(
                signers,
                seal,
                acroform,
                discriminators=discriminators,
                size=file_size,
                files_count=1,
            )
            if not session:
                session_id, session = create_session(
                    signers,
                    seal,
                    acroform=acroform,
                    title=title,
                    annot=annot,
                    discriminators=discriminators,
                    watchers=watchers,
                    create_session_custom_data=create_session_custom_data,
                )
                audit("create_session", "session={} signers={}".format(session_id, "|".join([sg[1] for sg in signers])))

        annex = uuidToObject(uuid=uid, unrestricted=True)
        context_uid_provider = getAdapter(annex, IContextUidProvider)
        context_uid = context_uid_provider.get_context_uid()
        # update data if adding same file to same session
        if annot["uids"].get(uid, -1) == session_id:
            logger.info("File with UID %s is already in session_id %s and data were updated!", uid, session_id)
            remove_files_from_session([uid], remove_empty_session=False)

        existing_files = [path.splitext(f["filename"])[0] for f in session["files"]]
        filename, ext = path.splitext(annex.file.filename or "no_filename.pdf")
        new_filename = get_correct_id(existing_files, filename)
        file_dict = PersistentMapping(
            {
                "scan_id": annex.scan_id,
                "filename": new_filename + ext,
                "title": annex.title or "no_title",
                "uid": uid,
                "context_uid": context_uid,
                "status": "",
            }
        )
        # Find the range of files already belonging to this context (if any)
        context_start_idx, context_end_idx = None, None
        for i, f in enumerate(session["files"]):
            if f["context_uid"] == context_uid:
                if context_start_idx is None:
                    context_start_idx = i
                context_end_idx = i
            elif context_start_idx is not None:
                break
        if context_start_idx is None:
            # No files from this context yet, append at end
            session["files"].append(file_dict)
        else:
            # Insert alongside other files from the same context, ordered by position
            context = uuidToObject(context_uid)
            if context is not None:
                uid_order = {a.UID(): idx for idx, a in enumerate(context.values())}
            else:
                uid_order = {}
            files = session["files"][context_start_idx: context_end_idx + 1]
            files.append(file_dict)
            session["files"][context_start_idx: context_end_idx + 1] = sorted(
                files, key=lambda f: uid_order.get(f["uid"], -1)
            )
        session["size"] = session.get("size", 0) + file_size
        annot["uids"][uid] = session_id
        annot["c_uids"].setdefault(context_uid, PersistentList()).append(uid)
        audit("add_files_to_session", "session={} context={} file={}".format(session_id, context_uid, uid))
        if session["client_id"] is None:
            # FIXME what if scan_id is None ?
            session["client_id"] = session["files"][0]["scan_id"][0:7]
            session["sign_id"] = "{}{:05d}".format(session["client_id"], session_id)
            if u"{sign_id}" in session["title"]:
                session["title"] = session["title"].replace(u"{sign_id}", session["sign_id"])
            if u"{session_id}" in session["title"]:
                session["title"] = session["title"].replace(u"{session_id}", str(session_id))
        session["last_update"] = datetime.now()
        if not sessions_used or sessions_used[-1][0] != session_id:
            sessions_used.append((session_id, session))
    return sessions_used


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
            "documentData": [
                {
                    "filename": filename,
                    "uniqueCode": "{}__{}".format(unique_code, fuid),
                    "docUuid": get_suid_from_uuid(fuid),
                }
                for unique_code, filename, z, fuid in files
            ],
            "imioAppSessionId": session["sign_id"],
            "sessionName": session["title"],
        }
    }
    # not mandatory now
    vat_number = get_esign_registry_vat_number(default="BE0000000097")
    data_payload["commonData"]["vatNumber"] = vat_number

    watchers = list(session.get("watchers", []))
    external_watchers = get_esign_registry_external_watchers()
    watchers.extend([ew for ew in external_watchers if ew not in watchers])
    signers = [fdic["email"] for fdic in session["signers"]]
    if signers:
        data_payload["signData"] = {
            "users": list(signers),
            "acroform": session["acroform"],
        }
        sign_code = get_esign_registry_sign_code()
        if sign_code:
            data_payload["signData"]["signCode"] = sign_code
        if watchers:
            data_payload["signData"]["watchers"] = watchers

    if session["seal"]:
        seal_email = get_esign_registry_seal_email()
        if not seal_email:
            logger.error("No seal email configured in registry.")
            return "_no_seal_email_"
        seal_code = get_esign_registry_seal_code()  # PADES_SEAL
        if not seal_code:
            logger.error("No seal code configured in registry.")
            return "_no_seal_code_"
        data_payload["sealData"] = {
            "users": [seal_email],
            # "placeholderName": "SCEAU",  # default
            "acroform": True,
            "watchers": watchers,
            "sealCode": seal_code,
        }

    # files_payload = {filename: file_content for z, filename, file_content, uid in files}
    files_payload = [("files", (filename, file_content)) for z, filename, file_content, _uid in files]

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


def create_session(
    signers,
    seal=False,
    acroform=True,
    title=None,
    annot=None,
    discriminators=(),
    watchers=(),
    create_session_custom_data=None,
):
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

    sessions[session_id] = PersistentMapping(
        {
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
                    PersistentMapping(
                        {"userid": userid, "email": email, "fullname": fullname, "position": position, "status": ""}
                    )
                    for userid, email, fullname, position in signers
                ]
            ),
            "watchers": PersistentList(watchers),
            "state": "draft",
            "title": title or _("Session ${id}", mapping={"id": session_id}),
            "returns": PersistentList(),
        }
    )
    if create_session_custom_data:
        for k, v in create_session_custom_data.items():
            sessions[session_id][k] = v
    return session_id, sessions[session_id]


def discriminate_sessions(signers, seal, acroform, discriminators=(), annot=None, size=0, files_count=0):
    """Discriminate sessions based on seal value and signers in the same order.

    :param signers: a list of signers, each is a quartet with userid, email, fullname and position text
    :param seal: seal boolean
    :param acroform: boolean value indicating if acroform is used
    :param discriminators: optional list of string discriminators
    :param annot: esign annotation, if not provided it will be fetched
    :param size: size in bytes of the files to be added to the session
    :param files_count: number of files to be added to the session
    :return: session id and session if found, or (None, None) if no session found
    """
    if not annot:
        annot = get_session_annotation()
    sessions = annot.get("sessions", {})
    max_session_size = get_esign_registry_max_session_size() * 1024 ** 2
    max_session_files = get_esign_registry_max_session_files()

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
        if set(discriminators) != set(session.get("discriminators", ())):
            continue
        signers_match = all(
            (userid, email) == (s["userid"], s["email"]) for (userid, email, z, z), s in zip(signers, session_signers)
        )
        if not signers_match:
            continue
        session_size = session.get("size", 0)
        session_files_count = len(session.get("files", []))
        if session_files_count + files_count >= max_session_files or size + session_size >= max_session_size:
            #  Mark it draft_full, so it will never be reconsidered for any future batch.
            session["state"] = "draft_full"
            session["last_update"] = datetime.now()
            if session_files_count + files_count > max_session_files or size + session_size > max_session_size:
                # Session can't accept this batch.
                continue

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


def get_file_info(session_id, file_uid, portal=None, readonly=True):
    """Return informations about a file (uid, title, filename, ...) in a session.

    :param session_id: the session id to return
    :param file_uid: the file UID in the session
    :param portal: portal if necessary to get the session annotation
    :param readonly: return a copy of stored data to avoid modifying it
    """
    session = get_session_info(session_id, portal=portal, readonly=readonly)
    if session:
        for file_info in session["files"]:
            if file_info["uid"] == file_uid:
                if readonly:
                    file_info = deepcopy(file_info)
                return file_info


def get_session_info(session_id, portal=None, readonly=True):
    """Return a session info for a given numbering.

    :param session_id: the session id to return
    :param portal: portal if necessary to get the session annotation
    :param readonly: return a copy of stored data to avoid modifying it
    """
    annot = get_session_annotation(portal=portal)
    session = {}
    if session_id in annot["sessions"]:
        session = annot["sessions"][session_id]
        if readonly:
            session = deepcopy(session)
    return session


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


def remove_files_from_session(files_uids, remove_empty_session=True):
    """Remove files from their corresponding sessions.

    :param files_uids: list of file UIDs to remove
    :param remove_empty_session: when the last file of a session is removed
           the session will be removed by default, except when False,
           the empty session is kept
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
        session["size"] = max(0, session.get("size", 0) - get_filesize(uid, session))
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
        if not session["files"] and remove_empty_session:
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
        root_url = get_esign_registry_file_url()

    if not root_url:
        raise Exception("No root URL provided for file download url.")
    if not short_uid:
        short_uid = get_suid_from_uuid(uid)
    return "{}/{}".format(root_url.strip("/"), short_uid), short_uid


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


def persistent_to_native(value):
    """Convert persistent object to native object recursively."""
    if isinstance(value, (PersistentMapping, dict)):
        return {k: persistent_to_native(v) for k, v in value.items()}
    elif isinstance(value, (PersistentList, list, tuple)):
        return [persistent_to_native(v) for v in value]
    return value


def get_state_description(state):
    """
    Get a human readable description for a given session state.

                  ┌─────────┐  (full)  ┌────────────┐
                  │  draft  │─────────▶│ draft_full │
                  └────┬────┘          └─────┬──────┘
                       │                     │
             (sent to Paraphéo)     (sent to Paraphéo)
                       │                     │
                       └──────────┬──────────┘
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
        "draft": u"The session is getting ready to be sent to Paraphéo by a signing manager.",
        "draft_full": u"The session is full (max size or max files reached) and is ready to be "
        u"sent to Paraphéo by a signing manager.",
        "sent": u"The session has been sent to Paraphéo.",
        "errored": u"The session encountered an error during its processing.",
        "to_sign": u"The session is ready to be signed in Paraphéo.",
        "signed": u"The session is finished but signed documents couldn't be sent back to the application.",
        "refused": u"The session has been cancelled because a signer refused a document.",
        "returned": u"The session is finished and signed documents are on the way back to the application.",
        "finalized": u"The session is finished and signed documents have been sent back to the application.",
    }.get(state, "")


def get_sessions_for(context_uid, readonly=True):
    """Returns a list of all sessions involving the provided context_uid"""
    annot = get_session_annotation()
    sessions = OrderedDict()
    for session_id, session in sorted(annot["sessions"].items()):
        if any(f["context_uid"] == context_uid for f in session["files"]):
            sessions[session_id] = deepcopy(session) if readonly else session
    return sessions
