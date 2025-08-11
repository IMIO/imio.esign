from imio.esign import E_SIGN_ROOT_URL

import requests


SESSION_URL = "imio/esign/v1/luxtrust/sessions"


def post_request(url, data=None, json=None, headers=None, files=None):
    """Post data to url.

    :param url: the url to post to
    :param data: a dict to consider
    :param json: a json serializable object
    :param headers: headers to use
    :param files: files to upload (dict or list of tuples)
    """
    kwargs = {}

    if files:
        kwargs["files"] = files
        if data:
            kwargs["data"] = data
        if headers:
            # Exclude Content-Type with multipart/form-data
            kwargs["headers"] = {k: v for k, v in headers.items() if k.lower() != "content-type"}
    else:
        kwargs["headers"] = headers or (
            {"Content-Type": "application/json"} if json else {"Content-Type": "application/x-www-form-urlencoded"}
        )
        if json:
            kwargs["json"] = json
        else:
            kwargs["data"] = data

    with requests.post(url, **kwargs) as response:
        if response.status_code != 200:
            print("Error while posting data '%s' to '%s': %s" % (kwargs, url, response.text))
        return response


def create_session(endpoint_url, files_uids, signers=(), seal=None, acroform=True):
    """Create a session with the given signers and files.

    :param files_uids: files uids in site
    :param endpoint_url: the endpoint URL to communicate with
    :param signers: a list of signers
    :param seal: a seal code, if any
    :param acroform: whether to use sign places
    :return: session information
    """
    session_url = "{}/{}".format(E_SIGN_ROOT_URL, SESSION_URL)
    # TODO must get files from annex uids
    files = []
    data_payload = {
        "commonData": {
            "endpointUrl": endpoint_url,
            "documentData": [{"filename": filename, "uniqueCode": unique_code} for unique_code, filename, _ in files],
            "imioAppSessionId": 1,
        }
    }

    if signers:
        data_payload["signData"] = {"users": list(signers), "acroform": acroform}

    if seal:
        data_payload["sealData"] = {"sealCode": seal}

    files_payload = [("files", (filename, file_content, "application/pdf")) for _, filename, file_content in files]

    # Headers avec autorisation
    headers = {"accept": "application/json", "Authorization": "Basic xxx"}

    ret = post_request(
        session_url, data={"data": str(data_payload).replace("'", '"')}, headers=headers, files=files_payload
    )
    return ret
