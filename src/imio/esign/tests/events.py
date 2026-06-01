# -*- coding: utf-8 -*-

from imio.esign.utils import remove_files_from_session


def on_annex_will_be_removed(annex, event):
    '''Called when an annex will be removed, before the removed event.'''
    # here annex is already unindexed
    remove_files_from_session([annex.UID()])
