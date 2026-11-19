# -*- coding: utf-8 -*-

from Acquisition import aq_base
from Acquisition import aq_parent
from collective.iconifiedcategory.utils import get_category_object
from imio.esign import _
from imio.esign.acroform import get_tag_ids
from imio.esign.acroform import update_file_acroform_tags
from imio.esign.adapters import ISignable
from imio.esign.config import get_esign_registry_check_annexes_tags_outside_session
from imio.esign.utils import get_file_info
from imio.esign.utils import get_session_annotation
from imio.esign.utils import get_sessions_for
from imio.esign.utils import remove_files_from_session
from os import path
from plone import api
from Products.CMFPlone.utils import safe_unicode
from zope.annotation.interfaces import IAnnotations


def on_categorized_annex_updated(annex, event):
    """When an annex is modified, update check if need to update esign session."""
    old_values = event.old_values
    # we are creating a new annex, not in a session
    if not old_values:
        return

    sessions = get_sessions_for(event.parent.UID(), readonly=False)
    if not sessions:
        return

    # make sure annex_uid is in a session
    annex_uid = annex.UID()
    file_infos = []
    for session_id in sessions:
        file_info = get_file_info(session_id, annex_uid)
        if file_info:
            file_infos.append(file_info)
    if not file_infos:
        return

    # here we are sure that annex is in a session, we need to update data
    # if something usefull changed, we will update the session
    new_values = event.new_values
    update = False
    checked_keys = ["title", "filesize", "relative_url"]
    for checked_key in checked_keys:
        if new_values[checked_key] != old_values[checked_key]:
            update = True
            break
    # check scan_id and filename
    if update is False:
        for file_info in file_infos:
            if file_info and (annex.scan_id != file_info["scan_id"] or annex.file.filename != file_info["filename"]):
                update = True
                break

    if update is True:
        for session_id, session in sessions.items():
            # size
            size_diff = new_values["filesize"] - old_values["filesize"]
            session["size"] += size_diff
            # title and filename
            for file_data in session["files"]:
                if file_data["uid"] == annex_uid:
                    file_data["title"] = new_values["title"]
                    file_data["scan_id"] = annex.scan_id
                    # filename changed, need to make sure new filename is unique
                    if annex.file.filename != file_data["filename"]:
                        existing_files = [
                            path.splitext(f["filename"])[0] for f in session["files"] if f["uid"] != annex_uid
                        ]
                        file_data["filename"] = ISignable(aq_parent(annex)).get_filename(
                            annex, existing_files=existing_files
                        )
                    # file_uid is only there one time per session
                    break

    # the file may have changed, update its stored acroform tags, the file is only read
    # again if its md5 changed. Limited updates (to_print, to_sign, ...) do not change the file
    if not event.limited:
        _update_acroform_tags(annex, sessions)


def _update_acroform_tags(annex, sessions):
    """Update the acroform tags stored for p_annex in the given p_sessions."""
    annex_uid = annex.UID()
    for session in sessions.values():
        for file_data in session["files"]:
            if file_data["uid"] == annex_uid:
                update_file_acroform_tags(file_data, annex)
                # file_uid is only there one time per session
                break


def _is_generated_from_template(obj):
    """Is the file of p_obj generated from a template?

    - the "conv_from_uid" attribute is set (collective.documentgenerator convert_and_save_file),
      it is set before the object is added so it is available when the creation events are notified;
    - the "documentgenerator" annotation is set (collective.documentgenerator generated document),
      it is set after the object is added, so available for later events only;
    - the published view is a document-generation view.
    """
    if getattr(aq_base(obj), "conv_from_uid", None) or IAnnotations(obj).get("documentgenerator"):
        return True
    published = getattr(obj, "REQUEST", None) and obj.REQUEST.get("PUBLISHED", None)
    return "document-generation" in getattr(published, "__name__", "")


def _signing_activated(annex):
    """Is signing (to_sign/signed) activated on the category group of p_annex?"""
    try:
        category = get_category_object(annex, getattr(aq_base(annex), "content_category", "_none"))
    except KeyError:
        return False
    return bool(category.get_category_group(category).signed_activated)


def _is_to_sign(annex):
    """Is p_annex to sign and not signed yet? The tags of a signed file are not relevant anymore."""
    base = aq_base(annex)
    return bool(getattr(base, "to_sign", False)) and not getattr(base, "signed", False)


def on_annex_added(annex, event):
    """Tell the user which acroform tags the file of a new annex holds, only when it is created to sign.

    The to_sign default value of the category is set after this subscriber is called (by
    collective.iconifiedcategory categorized_content_created) that then notifies an
    IconifiedAttrChangedEvent managed by on_annex_to_sign_changed. So here, to_sign only holds a value
    given at creation, in this case no IconifiedAttrChangedEvent is notified for to_sign.
    The file is not read for annexes that are not to sign.
    """
    if _is_to_sign(annex) and _signing_activated(annex):
        _show_acroform_tags(annex)


def on_annex_to_sign_changed(annex, event):
    """Tell the user which acroform tags the file of an annex holds when it becomes to sign,
    at creation (to_sign default value of the category) or when to_sign is changed."""
    if event.attr_name != "to_sign" or event.new_values.get("signed"):
        return
    if event.new_values.get("to_sign") and not event.old_values.get("to_sign"):
        _show_acroform_tags(annex)


def on_annex_modified(annex, event):
    """Tell the user which acroform tags the file of a modified annex to sign holds.

    An annex is mainly a title and a file, when it is edited, it is very often the file that changed,
    so any modification is considered (edit form, file uploaded again, ...).
    Changing to_print, to_sign, confidential, ... does not notify an IObjectModifiedEvent.
    """
    if _is_to_sign(annex):
        _show_acroform_tags(annex)


def _show_acroform_tags(annex):
    """Tell the user which acroform tags the file of p_annex holds.

    Malformed tags are warned about. Nothing is shown when the file was generated from a template,
    nor for an annex that is not in a session when the check_annexes_tags_outside_session setting is
    disabled (a lot of annexes to sign added at once). Annexes that are in a session are always checked.
    """
    if _is_generated_from_template(annex):
        return
    if not get_esign_registry_check_annexes_tags_outside_session() and \
            annex.UID() not in get_session_annotation()["uids"]:
        return
    numbers, seal_count, malformed = get_tag_ids(getattr(annex, "file", None))
    title = safe_unicode(annex.Title())
    tags = [u"Signer{}".format(nb) for nb in numbers] + seal_count * [u"SCEAU"]
    if tags:
        api.portal.show_message(
            _("Acroform tags detected in '${title}': ${tags}", mapping={"title": title, "tags": u", ".join(tags)}),
            request=annex.REQUEST,
            type="info",
        )
    if malformed:
        api.portal.show_message(
            _("Malformed acroform tags in '${title}': ${tags}", mapping={"title": title, "tags": u" ".join(malformed)}),
            request=annex.REQUEST,
            type="warning",
        )


def on_annex_will_be_removed(annex, event):
    """Called when an annex will be removed, before the removed event."""
    if event.object.portal_type == "Plone Site":
        return
    annex_uid = annex.UID()
    annot = get_session_annotation()
    if annex_uid in annot["uids"]:
        # remove it from any esign session, need done before removed from categorized_elements
        # nevertheless, here annex is already unindexed
        remove_files_from_session([annex_uid])
