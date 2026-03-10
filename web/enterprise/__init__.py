"""AMOS Enterprise Route Blueprints (stub).

Enterprise modules are available under commercial license from Merkuri LLC.
See ENTERPRISE.md for details.

In open-core mode, this module is a no-op — enterprise APIs return 404.
"""


def register_enterprise_blueprints(app):
    """Register enterprise blueprints.

    Open-core edition: no enterprise modules are included.
    Enterprise edition: install the private amos-enterprise overlay
    to populate this package with the full enterprise blueprints.
    """
    print("[AMOS] Edition: OPEN — enterprise blueprints not installed")
    print("[AMOS] See ENTERPRISE.md for licensing information")
