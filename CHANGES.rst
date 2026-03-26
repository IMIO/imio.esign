Changelog
=========


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

1.0a2 (2026-02-06)
------------------

- Removed `python_requires=">=3.7"` from `setup.py`.
  [gbastien]

1.0a1 (2026-02-06)
------------------

- Initial release.
  [sgeulette, gbastien, aduchene, cadam]
