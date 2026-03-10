# AMOS API Versioning

## Current Version
**v1** — All API endpoints are available at `/api/v1/...`

## Strategy
AMOS uses URL-based versioning with a dual-mount transition strategy:

- **Primary:** `/api/v1/...` — current, stable API
- **Deprecated:** `/api/...` — backward-compatible, same handlers

## Deprecation Policy
Unversioned `/api/` routes include deprecation headers:

```
Deprecation: true
Link: </api/v1/settings/locations>; rel="successor-version"
```

These routes will be removed in a future release. All new integrations should use `/api/v1/`.

## Upgrade Path
1. Update all API calls from `/api/...` to `/api/v1/...`
2. Monitor for `Deprecation: true` headers in responses
3. Unversioned routes will be removed in v6.0

## Versioning Rules
- Breaking changes require a new version (`/api/v2/`)
- Additive changes (new fields, new endpoints) are allowed within a version
- Removed or renamed fields require a version bump
- Page routes (`/`, `/dashboard`, `/settings`, etc.) are not versioned
- Auth routes (`/login`, `/logout`) are not versioned

## API Metrics
API metrics normalize versioned paths — `/api/v1/foo` and `/api/foo` are grouped
under the same endpoint for metrics tracking.
