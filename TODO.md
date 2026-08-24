# TODO

Task conventions: `todo-md-lite` skill. Shipped work is in `CHANGELOG.md`.

## Todo

| ID | Type | Status | Task | Depends | ADR | Triage |
| --- | --- | --- | --- | --- | --- | --- |
| core-bookmark-presentation | design | blocked | Decide and implement icons, concise links, and thumbnail previews | | 0005 | n |

## Future

| ID | Type | Status | Task | Depends | ADR | Triage |
| --- | --- | --- | --- | --- | --- | --- |
| core-actions-overflow | feature | pending | Move secondary bookmark actions into an overflow menu | core-bookmark-presentation | | n |
| core-filter-chips | feature | pending | Add removable active-filter chips | core-actions-overflow | | n |
| api-collection-query | feature | pending | Move collection filtering and pagination to the API | core-filter-chips | | n |
| core-results-sorting | feature | pending | Add sorting and a consolidated results toolbar | api-collection-query | | n |
| core-state-url | feature | pending | Persist collection state in the URL | core-results-sorting | | n |
| core-states-contextual | feature | pending | Add contextual empty and loading states | core-state-url | | n |
| core-metadata-entry | feature | pending | Improve folder and tag entry | core-states-contextual | | n |
| core-form-validation | feature | pending | Improve form validation and submission | core-metadata-entry | | n |
| import-web-redesign | feature | pending | Redesign browser bookmark import | core-form-validation | | n |
| core-modal-accessibility | fix | pending | Correct modal accessibility | import-web-redesign | | n |
| core-popup-accessibility | fix | pending | Correct popup and combobox accessibility | core-modal-accessibility | | n |
| core-visual-accessibility | fix | pending | Audit visual and touch accessibility | core-popup-accessibility | | n |
| test-web-redesign | test | pending | Validate all redesign workflows with A/B checks | core-visual-accessibility | | n |
