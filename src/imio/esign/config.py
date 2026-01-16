# -*- coding: utf-8 -*-

from plone import api


def get_registry_enabled(default=False):
    return api.portal.get_registry_record("imio.esign.enabled", default=default)


def get_registry_vat_number(default=""):
    return api.portal.get_registry_record("imio.esign.vat_number", default=default)


def get_registry_file_url(default=""):
    return api.portal.get_registry_record("imio.esign.file_url", default=default)


def get_registry_seal_code(default=""):
    return api.portal.get_registry_record("imio.esign.seal_code", default=default)


def get_registry_seal_email(default=""):
    return api.portal.get_registry_record("imio.esign.seal_email", default=default)


def get_registry_sign_code(default=""):
    return api.portal.get_registry_record("imio.esign.sign_code", default=default)


def set_registry_enabled(value):
    api.portal.set_registry_record("imio.esign.enabled", value)


def set_registry_vat_number(value):
    api.portal.set_registry_record("imio.esign.vat_number", value)


def set_registry_file_url(value):
    api.portal.set_registry_record("imio.esign.file_url", value)


def set_registry_seal_code(value):
    api.portal.set_registry_record("imio.esign.seal_code", value)


def set_registry_seal_email(value):
    api.portal.set_registry_record("imio.esign.seal_email", value)


def set_registry_sign_code(value):
    api.portal.set_registry_record("imio.esign.sign_code", value)
