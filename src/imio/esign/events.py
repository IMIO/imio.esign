# -*- coding: utf-8 -*-

from imio.esign.utils import get_sessions_for


def on_categorized_annex_updated(annex, event):
    '''When an annex is modified, update check if need to update esign session.'''
    old_values = event.old_values
    # we are creating a new annex, not in a session
    if not old_values:
        return

    sessions = get_sessions_for(event.parent.UID())
    if not sessions:
        return

    new_values = event.new_values
    # if something usefull changed, we will update the session
    update = False
    checked_keys = ['title', 'filesize', 'relative_url']
    for checked_key in checked_keys:
        if new_values[checked_key] != old_values[checked_key]:
            update = True
            break
    if update:
        annex_uid = annex.UID()
        for session in sessions:
            # size
            size_diff = new_values['filesize'] - old_values['filesize']
            session['size'] += size_diff
            # title and filename
            for file_data in session['files']:
                if file_data['uid'] == annex_uid:
                    file_data['title'] = new_values['title']
                    file_data['filename'] = annex.file.filename
