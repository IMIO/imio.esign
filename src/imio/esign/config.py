# -*- coding: utf-8 -*-

from plone import api


def get_esign_registry_enabled(default=False):
    return api.portal.get_registry_record("imio.esign.enabled", default=default)


def get_esign_registry_vat_number(default=""):
    return api.portal.get_registry_record("imio.esign.vat_number", default=default)


def get_esign_registry_file_url(default=""):
    return api.portal.get_registry_record("imio.esign.file_url", default=default)


def get_esign_registry_seal_code(default=""):
    return api.portal.get_registry_record("imio.esign.seal_code", default=default)


def get_esign_registry_seal_email(default=""):
    return api.portal.get_registry_record("imio.esign.seal_email", default=default)


def get_esign_registry_sign_code(default=""):
    return api.portal.get_registry_record("imio.esign.sign_code", default=default)


def get_esign_registry_parapheo_url(default=""):
    return api.portal.get_registry_record("imio.esign.parapheo_url", default=default)


def get_esign_registry_signing_users_email_content(default=""):
    return api.portal.get_registry_record("imio.esign.signing_users_email_content", default=default)


def get_esign_registry_max_session_size(default=100):
    return api.portal.get_registry_record("imio.esign.max_session_size", default=default)


def get_esign_registry_max_session_files(default=25):
    return api.portal.get_registry_record("imio.esign.max_session_files", default=default)


def get_esign_registry_external_watchers():
    value = api.portal.get_registry_record("imio.esign.external_watchers", default="")
    if not value:
        return []
    return [ew.strip() for ew in value.split(",") if ew.strip()]


def get_esign_registry_auto_cleanup_days(default=100):
    return api.portal.get_registry_record("imio.esign.auto_cleanup_days", default=default)


def set_esign_registry_enabled(value):
    api.portal.set_registry_record("imio.esign.enabled", value)


def set_esign_registry_vat_number(value):
    api.portal.set_registry_record("imio.esign.vat_number", value)


def set_esign_registry_file_url(value):
    api.portal.set_registry_record("imio.esign.file_url", value)


def set_esign_registry_seal_code(value):
    api.portal.set_registry_record("imio.esign.seal_code", value)


def set_esign_registry_seal_email(value):
    api.portal.set_registry_record("imio.esign.seal_email", value)


def set_esign_registry_sign_code(value):
    api.portal.set_registry_record("imio.esign.sign_code", value)


def set_esign_registry_parapheo_url(value):
    api.portal.set_registry_record("imio.esign.parapheo_url", value)


def set_esign_registry_signing_users_email_content(value):
    api.portal.set_registry_record("imio.esign.signing_users_email_content", value)


def set_esign_registry_max_session_size(value):
    api.portal.set_registry_record("imio.esign.max_session_size", value)


def set_esign_registry_max_session_files(value):
    api.portal.set_registry_record("imio.esign.max_session_files", value)


def set_esign_registry_external_watchers(value):
    api.portal.set_registry_record("imio.esign.external_watchers", value)


def set_esign_registry_auto_cleanup_days(value):
    api.portal.set_registry_record("imio.esign.auto_cleanup_days", value)


SIGNERS_EMAIL_CONTENT = u"""
<meta charset="UTF-8"><tal:global>
<p style="font-weight: bold;" tal:condition="nothing">!! Attention: ne pas modifier ceci directement mais passer
par "Source" !!</p>

<p>Bonjour <span tal:content="python: user_data['fullname']">FULLNAME</span>,</p>

<p>Vous avez été défini comme signataire dans une application IMIO (iA.Delib, iA.Docs, etc.).
<br />Avant de pouvoir signer des documents, vous devez activer votre compte auprès de Paraphéo.</p>

<p>Pour ce faire, il est nécessaire de s'y connecter une toute première fois en suivant ces étapes:</p>

<ol>
<li>Vous rendre sur <a href="#" tal:attributes="href parapheo_url">Paraphéo</a></li>
<li>Cliquer sur le mode de connexion "Portal d'authentification"</li>
<li>Entrer votre adresse email "<span tal:content="python: user_data['email']">EMAIL</span>" et cliquer
sur "Connexion"</li>
</ol>

<p>Si vous n'avez jamais défini votre mot de passe dans Wallonie Connect ou que vous l'avez oublié:</p>

<ol>
<li>Cliquer sur "Mot de passe oublié ?" (situé sous le champ "mot de passe")</li>
<li>Entrer à nouveau votre email et cliquer sur "Soumettre"</li>
<li>Consulter votre boîte mail qui doit contenir un mail intitulé "Réinitialiser le mot de passe"
(vérifier les spams au cas ou...)</li>
<li>Suivre les étapes pour configurer l'authentification par mobile</li>
</ol>

<p>En cas de besoin, n'hésitez pas à faire appel à votre référent interne Wallonie Connect !</p>

<p>Une fois votre mot de passe défini, vous pouvez poursuivre l'identification sur le site Paraphéo:</p>

<ol>
<li>Si besoin, répéter les 3 premières étapes du premier paragraphe</li>
<li>Entrer votre adresse email et&nbsp;votre mot de passe et cliquer sur "Connexion"</li>
<li>Entrer votre "code à usage unique" depuis votre mobile et cliquer sur "Connexion"</li>
<li>Une fois connecté dans Paraphéo, votre compte est validé et prêt à être utilisé dans une session de signature.</li>
</ol>

<p>Cordialement
<br />L'équipe IMIO</p>
</tal:global>"""
