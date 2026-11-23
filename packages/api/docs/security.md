# Security

How `example-api` protects requests. To report a vulnerability, see [SECURITY.md](../../../SECURITY.md). It builds on the [core library](../../core/docs/security.md), and the window mounts the same routes under its own protections ([window security](../../ui/docs/security.md)).

## Standalone API

When run alone (`python -m example_api`), the API protects itself:

- **API key:** protected routes need an `X-API-Key` header matching `EXAMPLE_API_API_KEYS`. The app will not start without a key unless `EXAMPLE_API_AUTH_MODE=none`, which is for local development only. Keys are compared in constant time.
- **Headers:** `nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, a restrictive content security policy, `Cache-Control: no-store` on `/api/` and HSTS over HTTPS.
- **Body limit:** requests declaring more than `EXAMPLE_API_MAX_BODY_BYTES` get `413`. Also set a limit at your reverse proxy, since chunked bodies have no declared size.
- **Docs hidden:** `/docs`, `/redoc` and `/openapi.json` are off unless `EXAMPLE_API_DOCS_ENABLED=true`.
- **Errors:** a `500` never shows details; they go to the log with the request ID.
- **Not included:** HTTPS, rate limiting, JWT and multi-user authentication, a database. Add them, or put the API behind a proxy, before exposing it publicly.

## Rules to keep when you add endpoints

1. Protect every route that is not a probe with the `authenticate` dependency.
2. Validate input with request models, set limits on lists and strings, and never build SQL, shell commands or file paths from request data.
3. Return response models, not raw objects, so internals and secrets cannot leak.
4. Keep secrets, keys and whole request bodies out of logs and error messages.
5. Keep CORS closed (`EXAMPLE_API_CORS_ORIGINS` empty) unless a browser client on another origin needs it, and list exact origins.

## Supply chain

Dependencies are locked in `uv.lock`. `audit-api.yml` runs `pip-audit` weekly, `security-api.yml` runs Semgrep and uploads the results to the Security tab, and the contract test fuzzes the running server in CI.
