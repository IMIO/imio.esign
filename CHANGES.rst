Changelog
=========


1.0b9 (unreleased)
------------------

- Added session info size on quick look.
  [chris-adam, sgeulette]
- Added "Open Paraphéo" button on sessions listing view.
  [chris-adam]

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
