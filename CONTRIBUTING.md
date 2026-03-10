# Contributing to AMOS

Thank you for your interest in contributing to AMOS! We welcome contributions from the robotics, defense, and autonomous systems communities.

## Scope

Contributions are accepted to the **open-core platform only**. Enterprise modules (cognitive engine, wargaming, swarm autonomy, ISR/ATR, COMSEC, TAK/Link-16/STANAG integrations, etc.) are commercially licensed and not open for external contribution.

Areas where contributions are especially welcome:
- **Plugins** — new hardware adapters, sensor integrations, autonomy modules
- **Bug fixes** — across the core platform
- **Documentation** — tutorials, API examples, deployment guides
- **Tests** — additional test coverage
- **Integrations** — ROS 2, MAVLink, MQTT, DDS adapters
- **Simulation** — new asset models, threat behaviors, environment models

## How to Contribute

1. **Fork** the repository
2. **Create a branch** from `main` (`git checkout -b feature/my-feature`)
3. **Make your changes** — follow the code style below
4. **Write tests** — all new features must include tests
5. **Run the test suite** — `python3 -m pytest tests/ -v --tb=short`
6. **Submit a Pull Request** against `main`

## Code Style

- Python 3.11+ — use type hints where practical
- Follow existing patterns in the codebase
- Keep functions focused and well-documented
- Validate all inputs to prevent errors
- Use environment variables for configuration, never hardcode secrets

## Testing

All PRs must pass the existing test suite. New features should include tests.

```bash
# Run all tests
python3 -m pytest tests/ -v --tb=short

# With coverage
python3 -m pytest tests/ --cov=web --cov=core --cov=services --cov-report=term-missing
```

## Plugin Development

Plugins are the preferred way to extend AMOS. See `docs/platform/AMOS_Plugin_SDK.md` for the full SDK guide. Copy `plugins/example_drone/` to start building your own.

## Developer Certificate of Origin (DCO)

By contributing to this project, you agree that your contributions are your own original work and that you have the right to submit them under the Apache 2.0 License.

All commits must include a `Signed-off-by` line:

```
Signed-off-by: Your Name <your@email.com>
```

You can add this automatically with `git commit -s`.

## Reporting Issues

- Use GitHub Issues for bugs and feature requests
- For security vulnerabilities, see [SECURITY.md](SECURITY.md)

## Contribution License and Commercial Rights

By contributing to AMOS, you agree that:

- Your contributions will be licensed under the Apache License 2.0
- **All contributions grant Merkuri LLC the right to use contributions commercially**, including in the AMOS Enterprise edition and any future Merkuri LLC products or services
- You represent that your contributions are your own original work

## Trademark

AMOS™ and Autonomous Mission Orchestration System™ are trademarks of Merkuri LLC. See [TRADEMARK.md](TRADEMARK.md) for the full trademark policy.
