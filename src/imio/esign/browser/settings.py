# -*- coding: utf-8 -*-
from imio.esign import _
from plone.app.registry.browser.controlpanel import ControlPanelFormWrapper
from plone.app.registry.browser.controlpanel import RegistryEditForm
from plone.z3cform import layout
from zope import schema
from zope.interface import Interface


class IImioEsignSettings(Interface):

    seal_code = schema.TextLine(
        title=_("Seal code"),
        description=_("Seal code given by eidas provider."),
        required=False,
    )

    seal_email = schema.TextLine(
        title=_("Seal email"),
        description=_("Email of the eidas provider account containing the seal image."),
        required=False,
    )


class ImioEsignSettings(RegistryEditForm):
    schema = IImioEsignSettings
    schema_prefix = "imio.esign"
    label = _("Imio Esign Settings")


ImioEsignSettingsView = layout.wrap_form(
    ImioEsignSettings, ControlPanelFormWrapper
)
