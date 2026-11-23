# Security

How `example-ui` protects requests in the window. To report a vulnerability, see [SECURITY.md](../../../SECURITY.md). The routes it mounts are described in the [API security notes](../../api/docs/security.md).

## Under Cornea

Cornea's `SecurityMiddleware` guards every mounted route, so the API adds no token of its own:

- the `Host` must be on the allow-list (the bound `127.0.0.1:<port>` only)
- state-changing requests (POST, PUT, PATCH, DELETE) must carry a matching `Origin`
- a one-time start-up token is exchanged for an `HttpOnly`, `SameSite=Strict` session cookie
- responses carry a strict content security policy and other protective headers (no inline scripts or styles)

`example_ui` therefore mounts the routes with API-key checks switched off. Never expose these routes any other way, and never bind the window to a public address.

## Rules to keep

1. Keep the frontend free of inline scripts and styles, and of `dangerouslySetInnerHTML` on untrusted data. ESLint's `security`, `no-unsanitized` and `jsx-a11y` plugins check this.
2. Treat native actions (the bridge) as a public interface: validate their input and keep them to what the page needs.
3. `--dev` relaxes the content security policy for Vite. Use it only while developing.
4. Keep secrets out of the frontend bundle, `ui/dist` and logs.
5. Keep `cornea-shell` and the frontend dependencies current (Dependabot opens the pull requests).

## Supply chain

Python dependencies are locked in `uv.lock` and the frontend's in `package-lock.json`. `audit-ui.yml` runs `pip-audit` and `npm audit` weekly, `security-ui.yml` runs Semgrep, and Dependabot updates both. The Windows executables can be signed (`SIGN_COMMAND`), and release files carry `SHA256SUMS.txt`.
