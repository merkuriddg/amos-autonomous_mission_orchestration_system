#!/usr/bin/env python3
"""AMOS Enterprise Overlay Uninstaller.

Removes enterprise files from amos-core and resets to open edition.

Usage:
    python uninstall.py /path/to/amos-core
    python uninstall.py /path/to/amos-core --dry-run    # preview only
"""

import argparse
import os
import sys

# Import the file manifest from install.py
from install import ENTERPRISE_FILES


def uninstall(core_path, dry_run=False):
    """Remove enterprise files from amos-core."""
    if not os.path.isfile(os.path.join(core_path, "web", "app.py")):
        print(f"ERROR: {core_path} does not look like an amos-core directory")
        return False

    mode = "DRY RUN" if dry_run else "UNINSTALL"
    print(f"[AMOS Enterprise] Mode: {mode}")
    print(f"[AMOS Enterprise] Core: {core_path}")

    removed, skipped = 0, 0
    for _, dst_rel in sorted(ENTERPRISE_FILES.items()):
        dst = os.path.join(core_path, dst_rel)

        if not os.path.exists(dst) and not os.path.islink(dst):
            skipped += 1
            continue

        is_link = os.path.islink(dst)
        label = "UNLINK" if is_link else "REMOVE"

        if dry_run:
            print(f"  WOULD {label}  {dst_rel}")
        else:
            os.remove(dst)
            print(f"  {label}  {dst_rel}")
        removed += 1

    # Reset AMOS_EDITION in .env
    env_file = os.path.join(core_path, ".env")
    if os.path.exists(env_file) and not dry_run:
        with open(env_file) as f:
            lines = [l for l in f.readlines() if not l.startswith("AMOS_EDITION=")]
        lines.append("AMOS_EDITION=open\n")
        with open(env_file, "w") as f:
            f.writelines(lines)
        print(f"\n  SET   AMOS_EDITION=open in .env")
    elif dry_run:
        print(f"\n  WOULD SET  AMOS_EDITION=open in .env")

    print(f"\n[AMOS Enterprise] Done: {removed} removed, {skipped} already absent")
    return True


def main():
    parser = argparse.ArgumentParser(description="AMOS Enterprise Overlay Uninstaller")
    parser.add_argument("core_path", help="Path to amos-core directory")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes only")
    args = parser.parse_args()

    success = uninstall(os.path.abspath(args.core_path), dry_run=args.dry_run)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
