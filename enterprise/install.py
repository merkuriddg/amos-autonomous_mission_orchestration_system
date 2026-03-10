#!/usr/bin/env python3
"""AMOS Enterprise Overlay Installer.

Symlinks (dev) or copies (production) enterprise files into the amos-core tree.
Run from the amos-enterprise/ directory with the path to amos-core as an argument.

Usage:
    python install.py /path/to/amos-core              # symlink mode (dev)
    python install.py /path/to/amos-core --copy        # copy mode (production)
    python install.py /path/to/amos-core --verify      # verify only, no changes
"""

import argparse
import os
import shutil
import sys

# Enterprise files to overlay — paths relative to repo root
ENTERPRISE_FILES = {
    # Services (Bundle 1 — Mission Intelligence)
    "services/cognitive_engine.py": "services/cognitive_engine.py",
    "services/nlp_mission_parser.py": "services/nlp_mission_parser.py",
    "services/commander_support.py": "services/commander_support.py",
    "services/learning_engine.py": "services/learning_engine.py",
    "services/red_force_ai.py": "services/red_force_ai.py",
    "services/wargame_engine.py": "services/wargame_engine.py",
    "services/threat_predictor.py": "services/threat_predictor.py",
    "services/coa_engine.py": "services/coa_engine.py",

    # Services (Bundle 2 — Advanced Swarm & Autonomy)
    "services/swarm_intelligence.py": "services/swarm_intelligence.py",
    "services/swarm_orchestrator.py": "services/swarm_orchestrator.py",
    "services/autonomy_manager.py": "services/autonomy_manager.py",

    # Services (Bundle 6 — Advanced Simulation & Effects)
    "services/kill_web.py": "services/kill_web.py",
    "services/isr_pipeline.py": "services/isr_pipeline.py",
    "services/effects_chain.py": "services/effects_chain.py",
    "services/environment_effects.py": "services/environment_effects.py",
    "services/space_domain.py": "services/space_domain.py",
    "services/hmt_engine.py": "services/hmt_engine.py",
    "services/atak_bridge.py": "services/atak_bridge.py",

    # Core modules (Bundle 4 — Secure Operations)
    "core/comsec.py": "core/comsec.py",
    "core/key_manager.py": "core/key_manager.py",
    "core/security_audit.py": "core/security_audit.py",

    # Core modules (Document Generation)
    "core/docs/opord_generator.py": "core/docs/opord_generator.py",
    "core/docs/conop_generator.py": "core/docs/conop_generator.py",

    # Enterprise integrations (Bundle 5 — Defense Integration)
    "integrations/tak_bridge.py": "integrations/tak_bridge.py",
    "integrations/link16_sim.py": "integrations/link16_sim.py",
    "integrations/vmf_adapter.py": "integrations/vmf_adapter.py",
    "integrations/stanag4586_adapter.py": "integrations/stanag4586_adapter.py",
    "integrations/nffi_adapter.py": "integrations/nffi_adapter.py",
    "integrations/ogc_client.py": "integrations/ogc_client.py",
    "integrations/kafka_adapter.py": "integrations/kafka_adapter.py",

    # Enterprise web blueprints
    "web/enterprise/intelligence.py": "web/enterprise/intelligence.py",
    "web/enterprise/warfare.py": "web/enterprise/warfare.py",
    "web/enterprise/security.py": "web/enterprise/security.py",
    "web/enterprise/defense.py": "web/enterprise/defense.py",
}


def install(core_path, enterprise_path, copy_mode=False, verify_only=False):
    """Install enterprise files into amos-core."""
    if not os.path.isfile(os.path.join(core_path, "web", "app.py")):
        print(f"ERROR: {core_path} does not look like an amos-core directory")
        return False

    mode = "VERIFY" if verify_only else ("COPY" if copy_mode else "SYMLINK")
    print(f"[AMOS Enterprise] Mode: {mode}")
    print(f"[AMOS Enterprise] Core:       {core_path}")
    print(f"[AMOS Enterprise] Enterprise: {enterprise_path}")

    ok, skip, fail = 0, 0, 0
    for src_rel, dst_rel in sorted(ENTERPRISE_FILES.items()):
        src = os.path.join(enterprise_path, src_rel)
        dst = os.path.join(core_path, dst_rel)

        if not os.path.exists(src):
            print(f"  SKIP  {src_rel} (not found in enterprise)")
            skip += 1
            continue

        if verify_only:
            exists = os.path.exists(dst)
            is_link = os.path.islink(dst)
            status = "OK (symlink)" if is_link else ("OK (file)" if exists else "MISSING")
            print(f"  {status:16s} {dst_rel}")
            ok += 1 if exists else 0
            fail += 0 if exists else 1
            continue

        # Ensure target directory exists
        os.makedirs(os.path.dirname(dst), exist_ok=True)

        # Remove existing file/link
        if os.path.exists(dst) or os.path.islink(dst):
            os.remove(dst)

        if copy_mode:
            shutil.copy2(src, dst)
            print(f"  COPY  {dst_rel}")
        else:
            os.symlink(os.path.abspath(src), dst)
            print(f"  LINK  {dst_rel}")
        ok += 1

    # Set AMOS_EDITION in .env
    if not verify_only:
        env_file = os.path.join(core_path, ".env")
        env_lines = []
        if os.path.exists(env_file):
            with open(env_file) as f:
                env_lines = [l for l in f.readlines() if not l.startswith("AMOS_EDITION=")]
        env_lines.append("AMOS_EDITION=enterprise\n")
        with open(env_file, "w") as f:
            f.writelines(env_lines)
        print(f"\n  SET   AMOS_EDITION=enterprise in .env")

    print(f"\n[AMOS Enterprise] Done: {ok} installed, {skip} skipped, {fail} failed")
    return fail == 0


def main():
    parser = argparse.ArgumentParser(description="AMOS Enterprise Overlay Installer")
    parser.add_argument("core_path", help="Path to amos-core directory")
    parser.add_argument("--copy", action="store_true", help="Copy files instead of symlink")
    parser.add_argument("--verify", action="store_true", help="Verify installation only")
    args = parser.parse_args()

    enterprise_path = os.path.dirname(os.path.abspath(__file__))
    success = install(
        os.path.abspath(args.core_path),
        enterprise_path,
        copy_mode=args.copy,
        verify_only=args.verify,
    )
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
