
from pathlib import Path
import pytest
import yaml
from sift.models import SessionTemplate
from sift.errors import SiftError

def test_template_cycle_detection(tmp_path):
    template_data = {
        "name": "Cycle Template",
        "description": "A template with a cycle",
        "phases": [
            {
                "id": "phase1",
                "name": "Phase 1",
                "prompt": "p1",
                "depends_on": "phase2"
            },
            {
                "id": "phase2",
                "name": "Phase 2",
                "prompt": "p2",
                "depends_on": "phase1"
            }
        ]
    }
    path = tmp_path / "cycle.yaml"
    with open(path, "w") as f:
        yaml.dump(template_data, f)
    
    with pytest.raises(SiftError, match="Circular dependency detected"):
        SessionTemplate.from_file(path)

def test_template_missing_dependency(tmp_path):
    template_data = {
        "name": "Missing Dep Template",
        "description": "A template with a missing dep",
        "phases": [
            {
                "id": "phase1",
                "name": "Phase 1",
                "prompt": "p1",
                "depends_on": "non-existent"
            }
        ]
    }
    path = tmp_path / "missing.yaml"
    with open(path, "w") as f:
        yaml.dump(template_data, f)
    
    with pytest.raises(SiftError, match="depends on non-existent phase"):
        SessionTemplate.from_file(path)
