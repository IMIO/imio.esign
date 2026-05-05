# -*- coding: utf-8 -*-

from imio.esign.utils import get_file_info
from imio.esign.utils import get_sessions_for
from imio.helpers.transmogrifier import get_correct_id
from os import path


def on_categorized_annex_updated(annex, event):
    '''When an annex is modified, update check if need to update esign session.'''
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
    checked_keys = ['title', 'filesize', 'relative_url']
    for checked_key in checked_keys:
        if new_values[checked_key] != old_values[checked_key]:
            update = True
            break
    # check scan_id and filename
    if update is False:
        for file_info in file_infos:
            if file_info and (annex.scan_id != file_info['scan_id'] or annex.file.filename != file_info['filename']):
                update = True
                break

    if update is True:
        for session_id, session in sessions.items():
            # size
            size_diff = new_values['filesize'] - old_values['filesize']
            session['size'] += size_diff
            # title and filename
            for file_data in session['files']:
                if file_data['uid'] == annex_uid:
                    file_data['title'] = new_values['title']
                    file_data['scan_id'] = annex.scan_id
                    # filename changed, need to make sure new filename is unique
                    if annex.file.filename != file_data['filename']:
                        existing_files = [path.splitext(f["filename"])[0]
                                          for f in session["files"]]
                        filename, ext = path.splitext(annex.file.filename)
                        new_filename = get_correct_id(existing_files, filename)
                        file_data['filename'] = new_filename + ext
                    # file_uid is only there one time per session
                    break
