#!/usr/bin/env python3
"""
Vérifications du dépôt Unreal sans moteur (JSON, fichiers requis, optionnel: PR assets).

Usage:
  python scripts/ci/validate_unreal_repo.py
  python scripts/ci/validate_unreal_repo.py --pr-assets
En PR sur GitHub, définir BASE_SHA / HEAD_SHA (ou laisser le workflow les remplir).
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

# Racine du dépôt = parent de scripts/
ROOT = Path(__file__).resolve().parents[2]
PROJ = ROOT / "LudumDare59"
UPROJECT = PROJ / "LudumDare59.uproject"
REQUIRED_INI = (
    PROJ / "Config" / "DefaultEngine.ini",
    PROJ / "Config" / "DefaultGame.ini",
)

# Au-delà de ce seuil, un .uasset / .umap modifié déclenche un avertissement (pas un échec).
WARN_BINARY_BYTES = 2 * 1024 * 1024
BINARY_EXT = {".uasset", ".umap", ".ubulk", ".utoc", ".ucas", ".pak"}


def _load_uproject() -> dict:
    if not UPROJECT.is_file():
        print(f"ERREUR: {UPROJECT} introuvable", file=sys.stderr)
        sys.exit(1)
    try:
        return json.loads(UPROJECT.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"ERREUR: JSON .uproject invalide: {e}", file=sys.stderr)
        sys.exit(1)


def _validate_core(data: dict) -> None:
    if data.get("FileVersion") is None:
        print("ERREUR: clé 'FileVersion' manquante dans le .uproject", file=sys.stderr)
        sys.exit(1)
    eng = data.get("EngineAssociation", "")
    print(f"UE EngineAssociation: {eng or '(non renseigné)'}")
    for p in REQUIRED_INI:
        if not p.is_file():
            print(f"ERREUR: fichier requis manquant: {p}", file=sys.stderr)
            sys.exit(1)
        rel = p.relative_to(ROOT)
        print(f"OK: {rel}")


def _git(args: list[str], cwd: Path) -> str:
    r = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    if r.returncode != 0:
        print(f"git {' '.join(args)} a échoué:\n{r.stderr}", file=sys.stderr)
        sys.exit(1)
    return r.stdout


def _pr_asset_warnings(base: str, head: str) -> int:
    """Retourne le nombre d'avertissements."""
    if not base or not head:
        print(
            "Avertissement PR assets: BASE_SHA/HEAD_SHA absents, étape ignorée.",
            file=sys.stderr,
        )
        return 0
    out = _git(["diff", "--name-only", f"{base}...{head}"], ROOT)
    names = [line.strip() for line in out.splitlines() if line.strip()]
    warnings = 0
    for name in names:
        path = ROOT / name
        ext = path.suffix.lower()
        if ext not in BINARY_EXT:
            continue
        if not path.is_file():
            continue
        size = path.stat().st_size
        if size >= WARN_BINARY_BYTES:
            print(
                f"AVERTISSEMENT: gros binaire Unreal modifié ({size // 1024} Ko): {name} — "
                "pensez à Git LFS si ce n'est pas déjà le cas."
            )
            warnings += 1
    if warnings == 0 and names:
        print("Aucun gros binaire Unreal (≥ seuil) dans le diff, ou pas de binaires listés.")
    return warnings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--pr-assets",
        action="store_true",
        help="Analyser le diff (BASE_SHA...HEAD_SHA) pour des gros binaires",
    )
    args = parser.parse_args()

    data = _load_uproject()
    _validate_core(data)
    print("Validation cœur du projet: OK")

    if args.pr-assets:
        base = os.environ.get("BASE_SHA", "")
        head = os.environ.get("HEAD_SHA", "")
        n = _pr_asset_warnings(base, head)
        if n:
            # Ne bloque pas la CI : information seulement
            print(f"Total avertissements binaires: {n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
