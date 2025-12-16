# -*- coding: utf-8 -*-
"""
Create a technical user in Luxtrust and upload an image.

This script allows to:
- check for existing users in the Luxtrust directory
- create a new user if it does not exist
- upload an acroform image for the user

Created from https://gitlab.imio.be/imio-api/apims-esign/-/blob/se-221-create_users_update_watermark-jean/notebooks/
COSI_eSign_put_acroform.ipynb
"""
from imio.pyutils.system import post_request
from imio.pyutils.system import stop

import argparse
import logging
import os.path
import requests


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("cosi_push")


def get_bearer_token(cosi_url, directory_alias, tenant_name, username, password):
    """Authentication and Bearer token get."""
    url = "{}/auth?directoryAlias={}".format(cosi_url, directory_alias)
    data = {
        "tenantName": tenant_name,
        "username": username,
        "password": password,
    }
    response = post_request(url, json=data, logger=logger, return_json=True)
    if not response:
        stop("No response from auth request", logger=logger)
    token = response.get("access_token")  # noqa F841
    if not token:
        stop("No token in auth response", logger=logger)
    return token


def get_users_from_directory(cosi_url, directory_alias, users, headers):
    """Get cosi users from email list."""
    payload = {
        "directoryAlias": directory_alias,
        "userIdList": users,
    }

    user_ids = post_request(url="{}/api/endusers/search".format(cosi_url), data=payload, headers=headers,
                            return_json=True)
    if not user_ids:
        return []
    for user in user_ids:
        logger.info("  - {}: {} ({})".format(user.get('id'), user.get('userId'), user.get('email')))
    return user_ids


def create_new_user(cosi_url, directory_alias, user, organisation_id, headers):
    """Create user."""
    firstname, lastname = user.split("@")
    payload = {
        "directoryAlias": directory_alias,
        "userId": user,
        "email": user,
        "firstName": firstname,
        "lastName": lastname,
        "localeCode": "FR",
        "phone": "+3200000000",
        "organisationId": organisation_id,
    }
    new_user = post_request(url="{}/api/endusers".format(cosi_url), json=payload, headers=headers)
    if new_user and new_user.get("id"):
        user_id = new_user.get("id")
        logger.info("New user created with id {}, email {}".format(user_id, user))
        return user_id
    else:
        stop("Cannot create user {}".format(user), logger=logger)
        return None


def upload_acroform(cosi_url, user_id, file_path, headers):
    """Upload image from path."""
    # 1. Get watermark ID for the user
    response = requests.get(url="{}/api/watermarks?targetId={}&type=USER".format(cosi_url, user_id), headers=headers)
    if not response.ok:
        stop("Error getting watermark for user {}".format(user_id), logger=logger)
    watermark_response = response.json()
    if not watermark_response or not isinstance(watermark_response, list) or len(watermark_response) == 0:
        stop("Error getting watermark for user {}".format(user_id), logger=logger)

    watermark_id = watermark_response[0].get("id")
    logger.debug("Watermark ID: {}".format(watermark_id))

    # 2. Upload image file
    with open(file_path, "rb") as f:
        file_content = f.read()

    filename = os.path.basename(file_path)
    multipart_data = [("image", (filename, file_content, "image"))]
    url = "{}/api/watermarks/{}?targetId={}&type=USER".format(cosi_url, watermark_id, user_id)

    result = requests.put(url=url, files=multipart_data, headers=headers)

    if result.ok:
        logger.info("Image uploaded for user {}".format(user_id))
    else:
        logger.error("Error uploading image for user {}: {}".format(user_id, result.text))


def main():
    """Fonction principale."""
    parser = argparse.ArgumentParser(description="Create user in Luxtrust and upload acroform image.")

    parser.add_argument("username", help="COSI username")
    parser.add_argument("password", help="COSI password")
    parser.add_argument("user_email", help="User email to check/create in Luxtrust")

    parser.add_argument("-f", "--file", help="File path to upload")
    parser.add_argument("-s", "--simulation", action="store_true", help="Simulation mode")
    parser.add_argument("--tenant-name", default="IMIO", help="Tenant name (default: IMIO)")
    parser.add_argument("--directory-alias", default="imio_internal", help="Directory alias (default: imio_internal)")
    parser.add_argument("--organisation-id", type=int, default=70, help="Organisation ID (default: 70 for staging)")
    parser.add_argument("--cosi-url", default="https://simplycosi-1-test.trustsigneurope.com", help="COSI URL")

    args = parser.parse_args()

    token = get_bearer_token(args.cosi_url, args.directory_alias, args.tenant_name, args.username, args.password)
    headers = {"Authorization": "Bearer {}".format(token)}

    logger.info("Checking if user '{}' exists...".format(args.user_email))
    user_ids = get_users_from_directory(args.cosi_url, args.directory_alias, [args.user_email], headers)

    user_id = None
    for u in user_ids:
        if u.get("userId") == args.user_email:
            user_id = u.get("id")
            logger.info("User '{}' found. We will reuse it".format(args.user_email))
            break

    if not user_id:
        logger.info("User '{}' not found. We will create it".format(args.user_email))
        if args.simulation:
            logger.info("Simulation mode: skipping user creation.")
        else:
            user_id = create_new_user(
                args.cosi_url,
                args.directory_alias,
                args.user_email,
                args.organisation_id,
                headers,
            )

    if args.file:
        logger.info("Upload image '{}'".format(args.file))
        if args.simulation:
            logger.info("Simulation mode: skipping image upload.")
        else:
            upload_acroform(args.cosi_url, user_id, args.file, headers)


if __name__ == "__main__":
    main()
