# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in AMOS, **do not open a public issue**.

Instead, please report it privately by emailing the maintainers directly.

Include:
- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

We will acknowledge receipt within 48 hours and provide a timeline for resolution.

## Supported Versions

Only the latest version on `main` is actively maintained.

## Security Considerations

AMOS is a mission operating system designed for autonomous robotic systems. Security is a core concern:

- All communications support AES-256-GCM encryption (see `core/comsec.py`)
- Key management via `core/key_manager.py`
- Security audit logging via `core/security_audit.py`
- Role-based access control on all API routes
- Password hashing via Werkzeug (bcrypt-compatible)

## Responsible Disclosure

We follow responsible disclosure practices. Please allow reasonable time for fixes before any public disclosure.
