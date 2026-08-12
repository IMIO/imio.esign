# -*- coding: utf-8 -*-

from imio.esign import _
from imio.esign.acroform import get_tag_ids
from imio.esign.utils import get_file_info
from imio.esign.utils import get_session_annotation
from imio.esign.utils import get_sessions_for
from imio.esign.utils import remove_files_from_session
from imio.helpers.transmogrifier import get_correct_id
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
                        existing_files = [path.splitext(f["filename"])[0] for f in session["files"]]
                        filename, ext = path.splitext(annex.file.filename)
                        new_filename = get_correct_id(existing_files, filename)
                        file_data["filename"] = new_filename + ext
                    # file_uid is only there one time per session
                    break


def on_annex_added(annex, event):
    """Tell the user which acroform tags the file of a new annex holds.

    Nothing is shown when the file holds no tag, or when the file was generated from a template.
    """

    def is_generated_from_template(obj):
        if IAnnotations(obj).get("documentgenerator"):
            return True
        published = getattr(obj, "REQUEST", None) and obj.REQUEST.get("PUBLISHED", None)
        return "document-generation" in getattr(published, "__name__", "")

    if is_generated_from_template(annex):
        return
    numbers, seal_count = get_tag_ids(getattr(annex, "file", None))
    tags = [u"Signer{}".format(nb) for nb in numbers if nb > 0] + seal_count * [u"SCEAU"]
    if not tags:
        return
    api.portal.show_message(
        _(
            "Acroform tags detected in '${title}': ${tags}",
            mapping={"title": safe_unicode(annex.Title()), "tags": u", ".join(tags)},
        ),
        request=annex.REQUEST,
        type="info",
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
