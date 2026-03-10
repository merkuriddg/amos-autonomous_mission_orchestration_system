# Security Policy

## Safety Disclaimer

**AMOS is a research and development platform and should not be used in safety-critical or operational environments without appropriate validation, testing, and certification.**

The simulation engine, autonomous behaviors, and decision-support tools are designed for development, training, and demonstration purposes. They have not been independently verified or validated for use in live military operations, safety-of-flight systems, or any application where failure could result in harm.

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.5.x   | ✓ Current |

## Reporting a Vulnerability

If you discover a security vulnerability in AMOS, please report it responsibly.

**Do not open a public GitHub issue for security vulnerabilities.**

Instead, email: **security@merkuri.com**

Please include:
- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

We will acknowledge receipt within 48 hours and provide a timeline for resolution.

## Security Considerations

- **Demo credentials** are included in the source code for development convenience. Change all passwords before any non-local deployment.
- **Database credentials** should be configured via environment variables (`AMOS_DB_USER`, `AMOS_DB_PASS`), not hardcoded.
- **Flask secret key** should be set via the `MOS_SECRET` environment variable in production.
- **COMSEC encryption** (AES-256-GCM) is available in the Enterprise edition for data-at-rest and data-in-transit protection.
- The default configuration binds to `0.0.0.0` — restrict this in production environments.

## Scope

This security policy applies to the AMOS open-core repository. For security issues related to AMOS Enterprise modules, contact enterprise@merkuri.com.
