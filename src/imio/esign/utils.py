from imio.esign import E_SIGN_ROOT_URL
from imio.helpers.content import uuidsToObjects
from plone.api.validation import mutually_exclusive_parameters

import json
import logging
import requests


logger = logging.getLogger("imio.esign")
SESSION_URL = "imio/esign/v1/luxtrust/sessions"


def create_session(endpoint_url, files_uids, signers=(), seal=None, acroform=True, b64_cred=None, session_id=None):
    """Create a session with the given signers and files.

    :param files_uids: files uids in site
    :param endpoint_url: the endpoint URL to communicate with
    :param signers: a list of signers
    :param seal: a seal code, if any
    :param acroform: whether to use sign places
    :param b64_cred: base64 encoded credentials for authentication
    :return: session information
    """
    session_url = "{}/{}".format(E_SIGN_ROOT_URL, SESSION_URL)
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

    ret = post_request(session_url, data={"data": json.dumps(data_payload)}, headers=headers, files=files_payload)
    return ret


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
