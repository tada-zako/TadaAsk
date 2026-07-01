# Console Project Workflow

This document summarizes the current Admin Console Project implementation. It is
an implementation guide for continuing frontend work, not a strict product
specification.

## Scope

Project is currently the first complete console-side frontend loop:

- route semantics are path based;
- shared project selection state is managed by Pinia;
- API wrappers stay thin;
- service code composes backend resources into view models;
- Vue pages render cleaned data and emit user actions from child panels.

The same shape can guide the upcoming Sources implementation.

## Route Semantics

Current routes:

- `/project`: Project landing.
- `/project/:projectUid`: Project overview.
- `/project/:projectUid/ask`: reserved Project Ask route.
- `/project/:projectUid/settings`: reserved Project Settings route.

`/project` does not auto-select the first project. It always shows the landing
state: an empty guide when no projects exist, or a project list plus create form
when projects exist.

`/project/:projectUid` treats `route.params.projectUid` as the source of truth.
When the uid is invalid, the page clears selection and redirects back to
`/project` with a lightweight error query.

## Data Flow

The current frontend flow is:

```text
console/api -> console/services -> Pinia store / view container -> child panels
```

Responsibilities:

- `console/api/projects.ts`: HTTP endpoint wrappers only.
- `console/services/project-workspace.ts`: project workspace orchestration,
  response unwrapping, display labels, derived metrics, and row view models.
- `console/stores/project.ts`: cross-component project list, selected project,
  loading state, and shared selection actions.
- `ProjectView.vue`: route-driven page container, workspace loading, mutation
  orchestration, and refresh after writes.
- `ProjectLandingState.vue`: landing UI and create-project form.
- `ProjectOverviewState.vue`: overview composition and panel layout.
- `ProjectLinkedSourcesPanel.vue`: linked-source display plus import/unbind/open
  UI events.
- `ProjectWidgetsPanel.vue`: widget display plus create/edit/delete/enable UI
  events.

Child panels should not call HTTP APIs directly. They receive cleaned data by
props and send user intent upward through emits.

## Workspace Loading

`loadProjectWorkspace(projectUid)` composes:

- project detail;
- project settings;
- linked project sources;
- project widgets;
- global sources for import candidates.

The service returns a single `ProjectWorkspaceViewModel`. The page does not need
to know backend response shapes beyond mutation inputs.

## Mutation Pattern

Project overview write actions use one pattern:

1. child panel emits an action;
2. `ProjectView.vue` calls the service function;
3. after success, `refreshWorkspace()` reloads workspace data;
4. metrics, health items, linked sources, and widget rows stay synchronized.

This favors clarity over local optimistic updates for MVP work.

## i18n Boundary

Console i18n uses `.ts` resources under `console/i18n/`.

Project service still owns derived display labels, so service-level labels and
fallback errors also go through i18n. When language changes, `ProjectView.vue`
refreshes the workspace view model so service-derived labels are regenerated.

The current language value is stored in localStorage. It is console-scoped and
does not affect the visitor widget.

## Current Tradeoffs

Known acceptable MVP tradeoffs:

- `ProjectView.vue` holds several route and mutation handlers. This is still
  acceptable while Project Ask and Project Settings are reserved.
- Error display is lightweight inline UI. A toast or global error UX can wait
  until more pages need the same pattern.
- Service-level i18n is practical for the current view model design, but future
  high-frequency locale switching may favor label keys or raw-data recomputation
  without API reloads.

## Guidance For Sources

Sources should follow the same broad shape:

- keep `console/api/sources.ts` as endpoint wrappers;
- add a Sources service when list/detail/create/indexing orchestration becomes
  real;
- introduce a Pinia store only for state that must be shared outside a single
  view;
- keep first implementation direct, then split panels when the view becomes
  heavy or repeated.
