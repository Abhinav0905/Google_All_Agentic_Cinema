"""Profile loader and manager for CueCheck."""

import json
from pathlib import Path
from typing import Dict, List, Optional

from engine.models import Profile

PROFILES_DIR = Path(__file__).resolve().parent.parent / "profiles"


def load_profile_from_path(path: Path) -> Profile:
    """Load and validate a Profile from a JSON file path."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return Profile.model_validate(data)


def load_profile(profile_id: str = "adult", custom_dir: Optional[Path] = None) -> Profile:
    """Load a profile by its ID (e.g. 'adult', 'kids')."""
    base_dir = custom_dir or PROFILES_DIR
    target_path = base_dir / f"{profile_id}.json"
    if not target_path.exists():
        # Fallback check if full filename was passed
        target_path = base_dir / profile_id
        if not target_path.exists():
            available = [p.stem for p in base_dir.glob("*.json")]
            raise FileNotFoundError(
                f"Profile '{profile_id}' not found in {base_dir}. Available: {available}"
            )
    return load_profile_from_path(target_path)


def list_profiles(custom_dir: Optional[Path] = None) -> List[Dict[str, str]]:
    """List available profiles with basic metadata."""
    base_dir = custom_dir or PROFILES_DIR
    profiles = []
    for p in sorted(base_dir.glob("*.json")):
        try:
            prof = load_profile_from_path(p)
            profiles.append({
                "id": prof.id,
                "name": prof.name,
                "description": prof.description,
            })
        except Exception:
            continue
    return profiles
