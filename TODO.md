# TODO

Task conventions: `todo-md-lite` skill. Shipped work is in `CHANGELOG.md`.

## Todo

| ID | Type | Status | Task | Depends | ADR | Triage |
| --- | --- | --- | --- | --- | --- | --- |

## Future

| ID | Type | Status | Task | Depends | ADR | Triage |
| --- | --- | --- | --- | --- | --- | --- |
| infra-schema-migrations | infra | pending | Add versioned SQLite schema migrations and backfills | | | n |
| core-actions-overflow | feature | pending | Move destructive and secondary bookmark actions into an overflow menu | | | n |
| core-view-density | feature | pending | Add a dense single-line view and make it the default | | | n |
| api-asset-caching | fix | pending | Add cache headers and ETags to local bookmark asset routes | | 0005 | n |
| core-metadata-diagnostics | feature | pending | Expose metadata fetch status and blocked-request explanations | | 0005 | n |
| core-navigation-disclosure | feature | pending | Prioritize taxonomy facets and collapse raw Sources by default | | | n |
| infra-ab-controls | fix | pending | Move A/B variant controls outside the product header | | 0004 | n |
| api-collection-query | feature | pending | Move collection filtering, sorting, paging, and totals to the API | | | n |
| core-bookmark-lifecycle | design | pending | Decide Inbox, Archive, and deletion lifecycle rules | | | n |
| core-domain-taxonomy | design | pending | Decide permanent domains separately from imported folders | | | n |
| core-health-policy | design | pending | Decide link-health checks, retention, and network controls | | | n |
| core-visit-policy | design | pending | Decide visit tracking, retention, and privacy rules | | | n |
| core-lifecycle-storage | feature | pending | Persist lifecycle states and default new saves to Inbox | infra-schema-migrations, core-bookmark-lifecycle | | n |
| core-tag-taxonomy | refactor | pending | Normalize tags and support indexed multi-tag intersections | infra-schema-migrations | | n |
| core-content-formats | feature | pending | Store and classify bookmark content formats | infra-schema-migrations | | n |
| core-domain-storage | feature | pending | Store permanent domains separately from imported folders | infra-schema-migrations, core-domain-taxonomy | | n |
| api-search-index | feature | pending | Add indexed term-intersection bookmark search | infra-schema-migrations | | n |
| core-link-health | feature | pending | Check link health and provide a Dead Links view | infra-schema-migrations, core-health-policy | | n |
| core-visit-tracking | feature | pending | Record bookmark visits and provide a Most Visited view | infra-schema-migrations, core-visit-policy | | n |
| core-bulk-triage | feature | pending | Bulk tag, move, classify, and archive bookmarks | core-lifecycle-storage, core-tag-taxonomy, core-content-formats, core-domain-storage | | n |
| core-delete-recovery | feature | pending | Replace immediate hard deletion with recoverable deletion | core-lifecycle-storage | | n |
| core-filter-chips | feature | pending | Add multi-value filter chips and a global filter reset | api-collection-query | | n |
| core-results-sorting | feature | pending | Add sorting, page jump, and a consolidated results toolbar | api-collection-query | | n |
| core-result-grouping | feature | pending | Group repetitive collection results by source or similarity | api-collection-query | | n |
| core-metadata-scheduling | refactor | pending | Prioritize visible bookmarks and bound metadata refresh work | api-collection-query | 0005 | n |
| core-command-palette | feature | pending | Add Cmd+K and Ctrl+K search, navigation, and actions | api-search-index | | n |
| core-state-url | feature | pending | Persist collection query, facets, sorting, and page state in the URL | core-filter-chips, core-results-sorting | | n |
| core-saved-views | feature | pending | Save named combinations of filters, sorting, and queries | core-state-url | | n |
| core-states-contextual | feature | pending | Add contextual Inbox, filtered, empty, and loading states | core-lifecycle-storage, core-filter-chips | | n |
| core-metadata-entry | feature | pending | Add autocomplete for normalized tags, domains, and formats | core-tag-taxonomy, core-content-formats, core-domain-storage | | n |
| core-form-validation | feature | pending | Improve form validation and submission | core-metadata-entry | | n |
| import-web-redesign | feature | pending | Redesign browser bookmark import | core-form-validation | | n |
| core-modal-accessibility | fix | pending | Correct modal accessibility | import-web-redesign | | n |
| core-popup-accessibility | fix | pending | Correct popup and combobox accessibility | core-modal-accessibility | | n |
| core-visual-accessibility | fix | pending | Audit visual and touch accessibility | core-popup-accessibility | | n |
| test-library-scale | test | pending | Validate 1,500-bookmark paging and cold-cache workflows | core-view-density, api-asset-caching, core-metadata-scheduling | | n |
| test-web-redesign | test | pending | Validate all redesign workflows with A/B checks | core-visual-accessibility, core-bulk-triage, core-saved-views, core-command-palette | | n |
