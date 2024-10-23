import json
from pathlib import Path


def load_test_data(filename: str) -> list[dict]:
    file = Path(__file__).parent / (filename + ".json")
    with file.open('r') as f:
        return json.load(f)
