# -*- coding: utf-8 -*-
from natsort import humansorted
from plone import api
from Products.CMFPlone.utils import safe_unicode
from zope.interface import implementer
from zope.schema.interfaces import IVocabularyFactory
from zope.schema.vocabulary import SimpleTerm
from zope.schema.vocabulary import SimpleVocabulary


@implementer(IVocabularyFactory)
class ActiveSignersVocabulary(object):
    """Vocabulary of held_positions whose usages include 'signer'.

    To override in a downstream app, register your own IVocabularyFactory
    under the same name in configure.zcml or overrides.zcml:

        <utility
            name="imio.esign.ActiveSignersVocabulary"
            component=".vocabularies.MySignersVocabulary"
            provides="zope.schema.interfaces.IVocabularyFactory" />
    """

    def __call__(self, context):
        catalog = api.portal.get_tool("portal_catalog")
        brains = catalog.unrestrictedSearchResults(
            portal_type="held_position",
            usages="signer",
        )
        terms = []
        for brain in brains:
            hp = brain._unrestrictedGetObject()
            person = hp.get_person()
            if person is None or not person.userid:
                continue
            user = api.user.get(userid=person.userid)
            if user is None:
                continue
            email = safe_unicode(user.getProperty("email", u"")).strip()
            if not email:
                continue
            uid = brain.UID
            title = safe_unicode(hp.get_full_title(first_index=1))
            terms.append(SimpleTerm(value=uid, token=uid, title=title))
        terms = humansorted(terms, key=lambda t: t.title)
        return SimpleVocabulary(terms)
