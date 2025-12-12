# -*- coding: utf-8 -*-
from imio.esign import _
from plone.app.registry.browser.controlpanel import ControlPanelFormWrapper
from plone.app.registry.browser.controlpanel import RegistryEditForm
from plone.z3cform import layout
from zope import schema
from zope.interface import Interface
from zope.interface import Invalid


def validate_vat_number(va_nb):
    """Validate the VAT number format. It should start with BE followed by 10 digits,
    with the last 2 digits being a control checksum of the first 8 digits."""
    if not va_nb:
        return True

    # Check format: BE followed by 10 digits
    if not va_nb.startswith('BE'):
        raise Invalid(_("VAT number must start with 'BE'"))

    if len(va_nb) != 12:
        raise Invalid(_("VAT number must be 12 characters (BE + 10 digits)"))

    digits = va_nb[2:]
    if not digits.isdigit():
        raise Invalid(_("VAT number must contain 10 digits after 'BE'"))

    # Validate checksum: last 2 digits should be 97 - (first 8 digits modulo 97)
    first_eight = int(digits[:8])
    control = int(digits[8:10])
    expected_control = 97 - (first_eight % 97)

    if control != expected_control:
        raise Invalid(_("Invalid VAT number: checksum verification failed"))

    return True


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

    vat_number = schema.TextLine(
        title=_("VAT number"),
        description=_("VAT number used for esign billing (BE0123456789)."),
        constraint=validate_vat_number,
        required=True,
    )


class ImioEsignSettings(RegistryEditForm):
    schema = IImioEsignSettings
    schema_prefix = "imio.esign"
    label = _("Imio Esign Settings")


ImioEsignSettingsView = layout.wrap_form(
    ImioEsignSettings, ControlPanelFormWrapper
)
