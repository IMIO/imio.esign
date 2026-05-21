# -*- coding: utf-8 -*-
from imio.esign import _
from imio.esign.config import get_esign_registry_seal_code
from imio.esign.utils import create_session
from imio.helpers.content import uuidToObject
from plone import api
from plone.autoform import directives
from plone.autoform.form import AutoExtensibleForm
from plone.z3cform.layout import wrap_form
from z3c.form import button
from z3c.form import form
from z3c.form.browser.checkbox import CheckBoxFieldWidget
from zope import schema
from zope.component import queryUtility
from zope.interface import implementer
from zope.interface import Interface
from zope.schema.interfaces import IContextSourceBinder
from zope.schema.interfaces import IVocabularyFactory
from zope.schema.vocabulary import SimpleVocabulary


@implementer(IContextSourceBinder)
class SignersSourceBinder(object):
    """Source binder that delegates to the named vocabulary."""

    def __call__(self, context):
        factory = queryUtility(
            IVocabularyFactory, name=u"imio.esign.ActiveSignersVocabulary"
        )
        if factory is not None:
            return factory(context)
        return SimpleVocabulary([])


class ICreateCustomSession(Interface):

    title = schema.TextLine(
        title=_(u"Session title"),
        required=False,
    )

    signers = schema.Set(
        title=_(u"Signers"),
        required=True,
        value_type=schema.Choice(
            source=SignersSourceBinder(),
        ),
    )
    directives.widget("signers", CheckBoxFieldWidget)

    seal = schema.Bool(
        title=_(u"Seal"),
        required=False,
        default=False,
    )


class CreateCustomSessionForm(AutoExtensibleForm, form.Form):

    schema = ICreateCustomSession
    ignoreContext = True
    label = _(u"Create custom session")
    css_class = u"create-custom-session"

    def get_default_seal(self):
        """Return the default value for the seal field.
        Override in a subclass to change the default.
        """
        return False

    def get_default_title(self):
        """Return the default value for the title field.
        Override in a subclass to change the default.
        """
        return _(u"Custom session")

    def extract_signer_info(self, value):
        """Extract signer info from a held_position UID.

        Returns a (userid, email, fullname, position) tuple, or None
        if the held_position does not exist or has no linked user.
        """
        hp = uuidToObject(value, unrestricted=True)
        if hp is None:
            return None
        person = hp.get_person()
        if person is None or not person.userid:
            return None
        user = api.user.get(userid=person.userid)
        if user is None:
            return None
        email = user.getProperty("email", "")
        fullname = person.get_title(include_person_title=False)
        position = hp.get_full_title(first_index=1)
        return (person.userid, email, fullname, position)

    def updateFields(self):
        super(CreateCustomSessionForm, self).updateFields()
        if not get_esign_registry_seal_code():
            self.fields = self.fields.omit("seal")

    def updateWidgets(self):
        super(CreateCustomSessionForm, self).updateWidgets()
        if not self.widgets["title"].value:
            self.widgets["title"].value = self.get_default_title()
        if "seal" in self.widgets:
            if self.get_default_seal():
                self.widgets["seal"].value = ("selected",)

    @button.buttonAndHandler(_(u"Create"), name="create")
    def handleCreate(self, action):
        data, errors = self.extractData()
        if errors:
            return

        signers = []
        for value in data.get("signers", []):
            info = self.extract_signer_info(value)
            if info is not None:
                signers.append(info)

        if not signers:
            api.portal.show_message(
                _(u"No valid signers selected!"),
                request=self.request,
                type="warning",
            )
            return

        seal = data.get("seal", False)
        title = data.get("title") or u""

        create_session(signers=signers, seal=seal, title=title)

        api.portal.show_message(
            _(u"Custom session created successfully!"),
            request=self.request,
            type="info",
        )
        self.request.RESPONSE.redirect(
            api.portal.get().absolute_url() + "/@@parapheo"
        )

    @button.buttonAndHandler(_(u"Cancel"), name="cancel")
    def handleCancel(self, action):
        self.request.RESPONSE.redirect(
            api.portal.get().absolute_url() + "/@@parapheo"
        )


CreateCustomSessionFormView = wrap_form(CreateCustomSessionForm)
