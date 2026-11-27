Changelog
=========

1.0.7 (unreleased)
------------------

- In `utils.add_files_to_session`, reuse the session used for the previous file
  if it is still a draft that may receive the file instead of calling
  `utils.discriminate_sessions` (that walks every sessions) for every file,
  sessions are discriminated again when the session is full.
  Added `utils.session_may_receive` to check the session limits, used by
  `utils.discriminate_sessions` and `utils.add_files_to_session`.
  [gbastien]
- Added parameter `annex` to `utils.get_filesize` so the annex is not looked up
  again when it is already available, used by `utils.add_files_to_session` that
  was getting every annex twice from the catalog.
  [gbastien]
- In `utils.add_files_to_session`, a file that is not found is skipped (and logged)
  instead of failing with an `AttributeError` (and possibly creating an empty session).
  [gbastien]


1.0.6 (2026-11-26)
------------------

- Discriminators must be a tuple of strings, this is checked by `utils.check_discriminators`
  in `add_files_to_session`, `create_session` and `discriminate_sessions` that raise a
  `TypeError` otherwise. Discriminators are compared as sets so a string was compared as
  a set of characters and different strings made of the same characters (like UIDs) were
  added to the same session. `ISignable.get_discriminators` must return a tuple.
  Added `utils.get_session_discriminators` to get discriminators stored on a session
  as a tuple, sessions created before may store a list or a string.
  [gbastien]


1.0.5 (2026-11-19)
------------------

- Added setting to enforce signers order (PARAF-527).
  [chris-adam]
- The signers order (`imio.esign.signers` vocabulary) holds held position UIDs instead of userids,
  `SignableAdapter.sort_signers` matches signers on the userids of the persons of these held
  positions, see `SignableAdapter.get_signers_order_userids` (PARAF-527).
  [gbastien]
- When the signers order is enforced, the `Signers` column header of the sessions
  table (`@@parapheo`) is `Signers (signing order)` with a help icon explaining
  that the signing order may be different from the order of the signers
  on the document (PARAF-527).
  [gbastien]
- When the signers order is enforced, the `Signers` label of the session info
  viewlet displayed on an element is also `Signers (signing order)` with the same
  help icon as the `Signers` column of the sessions table, see `table.signers_label`
  and `table.signers_order_help_icon` (PARAF-527).
  [gbastien]


1.0.4 (2026-11-16)
------------------

- Updated `plone.restapi: Use REST API` permission roles.
  [sgeulette]

1.0.3 (2026-09-14)
------------------

- Do not let `Recreate session` when it is `sent` or `signed`.
  [gbastien]
- Formalised the sent filename generation in `ISignable.get_filename` (PARAF-550).
  [chris-adam]

1.0.2 (2026-08-24)
------------------

- Added `RecreateSessionView.get_create_session_custom_data` to compute
  `create_session_custom_data` using first element of old session.
  Moreover, `Recreate session` action is hidden when session is `to_sign`.
  [gbastien]
- Added a default implementation for the `ISignable` adapter so all relevant
  methods have a default implementation. Overrides should inherit from it.
  [gbastien]
- More accurate translation for `sent` state `(?)` tooltip.
  [gbastien]

1.0.1 (2026-08-20)
------------------

- Add a final `.` at end of help title message displayed when hovering the
  `Signed/Not signed` icon in the UI.
  [gbastien]
- Improved file ordering in session.
  [chris-adam]
- Displayed who refused a session and his comment in the state help tooltip (PARAF-457).
  [chris-adam]

1.0.0 (2026-08-14)
------------------

- Avoided error when deleting site.
  [sgeulette]
- Improved ExternalSessionFeedback audit.
  [chris-adam]
- When a session status is received as completed, mark each signer as signed.
  [sgeulette]
- Added action RecreateSession (PARAF-420).
  [chris-adam]
- Handled return code 60: external session deleted
  [sgeulette]
- Displayed special characters and dates correctly in session annotation info view (PARAF-508).
  [chris-adam]

1.0b10 (2026-06-18)
-------------------

- Fixed session size computation when an annex is deleted.
  [gbastien]
- In `@@session-annotation-info` display `UID` next to link to element.
  [gbastien]
- Display annex description in `@@parapheo` quick look column.
  Added parameter `session_id` to `SessionFilesView.__call__` to avoid having to
  get it from the `request`, we receive it directly as integer.
  [gbastien]
- Added red/green icon next to signers to show if not signed or signed.
  In info viewlet, display `signed` in green.
  [gbastien]

1.0b9 (2026-06-02)
------------------

- Added session info size on quick look.
  [chris-adam, sgeulette]
- Added "Open Paraphéo" button on sessions listing view.
  [chris-adam]
- Added parameter to define session files number limit
  [sgeulette]

1.0b8 (2026-05-08)
------------------

- Set registry parapheo_url following is_test_url.
  [sgeulette]
- Override `check_permission` method to `ExternalSessionFeedbackPost` service
  to ignore `UseRESTAPI` permission and only check the validity of the authentication token.
  [chris-adam]

1.0b7 (2026-04-02)
------------------

- Adapted `SessionsListingView.get_sessions` to not modify the annotation
  causing a DB write at each access to `@@parapheo`.
  [gbastien]

1.0b6 (2026-04-01)
------------------

- Use existing `utils.get_session_info` instead
  `FilesBelongingToAGivenSession.get_session` to get the session in
  `files-belonging-to-a-given-session` adapter.
  [gbastien]
- Fixed table rendering when a user signed causing `UnicodeDecodeError`.
  [gbastien]

1.0b5 (2026-04-01)
------------------

- Avoid `UnicodeDecodeError` in `SignersColumn` if signers
  contain mixed encoding values.
  [gbastien]

1.0b4 (2026-03-27)
------------------

- Renamed imio.esign config functions.
  [cadam]
- Highlight `draft` session in table view and viewlet, use `Id` as
  column header instead `identifier` so it is more narrow and
  make `sessions` view columns sortable.
  [gbastien]

1.0b3 (2026-03-26)
------------------

- In sessions annotation, use a `PersistentMapping` instead a `dict` to store
  `signers` informations as the `status` will be updated.
  [gbastien]

1.0b2 (2026-03-26)
------------------

- Redo release.
  [gbastien]

1.0b1 (2026-03-26)
------------------

- Disable sorting on checkbox column of `@@signing-users-csv`.
  [gbastien]
- Added SessionAnnotationInfoView.
  [chris-adam,sgeulette]
- Open the `@@session-annotation-info` in an overlay.
  [gbastien]
- Fixed audit message when firing action remove context
  [chris-adam]

1.0a4 (2026-03-24)
------------------

- Redirect to `HTTP_REFERER` instead context's url after
  `add/remove/remove item` actions.
  [gbastien]
- Added `odd/even` class on `<li>` of the files `collapsible` on sessions view.
  [gbastien]
- Added separated fingerpointing log.
  [chris-adam]

1.0a3 (2026-03-20)
------------------

- Replaced external_session_link p by span.
  [sgeulette]
- Switched basic auth to jwt.
  [chris-adam]
- Added files size session discriminator
  [chris-adam, sgeulette]
- Added title attribute on session state for better description
  [chris-adam]
- Raise Unauthorized if accessing @@parapheo and not available
  [gbastien]
- Added action to remove a single item from session.
  [chris-adam]
- Improved signing-users-csv template to include emails sending information.
  [chris-adam, sgeulette]
- Used API_ROOT_URL env variable
  [sgeulette]
- Style sessions state-column to display a question circle.
  [gbastien]
- Avoided duplicated filenames and kept files ordering in session.
  [sgeulette]
- Added seal column on @@parapheo.
  [chris-adam]
- Added external watchers for esign sessions.
  [chris-adam, sgeulette]
- Added possibility to have elements of the same context to belong to different sessions.
  [chris-adam]
- Manage file added again to same session, data is updated.
  [gbastien]
- Configured the `@@remove-from-esign-session` the same way as `@@remove-item-from-esign-session`
  so relying on an `available` method to show it only if a context is in a session.
  [gbastien]
- Fixed faceted viewlet broken because sessions format changed from list to OrderedDict.
  [gbastien]
- Turned file info in session annotation from `dict` to `PersistentMapping`.
  Entire annotation structure is now persistent, remove `_p_changed`.
  [gbastien]
- Use `@CachedProperty` for `FacetedSessionInfoViewlet.sessions` and `ItemSessionInfoViewlet.sessions`.
  [gbastien]
- Files added to session are inserted alongside other files from the same context, ordered by position.
  [chris-adam]

1.0a2 (2026-02-06)
------------------

- Removed `python_requires=">=3.7"` from `setup.py`.
  [gbastien]

1.0a1 (2026-02-06)
------------------

- Initial release.
  [sgeulette, gbastien, aduchene, cadam]
