"""Evaluation script placeholder."""

import json
from pathlib import Path


def main() -> None:
    """Load expected evaluation data and print placeholder results."""
    expected_path = Path(__file__).resolve().parents[2] / "data" / "expected.json"
    if not expected_path.exists():
        raise FileNotFoundError(f"Evaluation data not found: {expected_path}")
    expected = json.loads(expected_path.read_text(encoding="utf-8"))
    for item in expected:
        print(f"FAIL: {item} (TODO: evaluation is not implemented)")


if __name__ == "__main__":
    main()
