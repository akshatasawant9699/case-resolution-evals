"""Deterministic checks on the platform-neutral spec. No API keys needed."""

import importlib.util
import json
from pathlib import Path

import jsonschema
import pytest
import yaml

SPEC = Path(__file__).resolve().parents[2] / "spec"
SCHEMA = json.loads((SPEC / "task.schema.json").read_text())
TASK_FILES = sorted((SPEC / "tasks").glob("*.yaml"))
PERSONAS = yaml.safe_load((SPEC / "personas" / "personas.yaml").read_text())
RUBRICS = {p.stem for p in (SPEC / "rubrics").glob("*.md")}


def test_schema_is_valid():
    jsonschema.Draft202012Validator.check_schema(SCHEMA)


def test_template_matches_schema():
    template = yaml.safe_load((SPEC / "tasks" / "_TEMPLATE.yaml.example").read_text())
    jsonschema.validate(template, SCHEMA)


@pytest.mark.parametrize("path", TASK_FILES, ids=lambda p: p.stem)
def test_task_is_valid(path):
    task = yaml.safe_load(path.read_text())
    jsonschema.validate(task, SCHEMA)
    assert task["id"] == path.stem, "file name must match task id"
    assert task["persona"] in PERSONAS
    assert set(task.get("rubrics", [])) <= RUBRICS


def test_seed_data_is_reproducible():
    spec = importlib.util.spec_from_file_location("generate_seeds", SPEC / "seeds" / "generate_seeds.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    for table, rows in mod.generate().items():
        committed = json.loads((SPEC / "seeds" / "data" / f"{table}.json").read_text())
        assert rows == committed, f"{table}.json is stale; rerun generate_seeds.py"


def test_policy_articles():
    policies = yaml.safe_load((SPEC / "seeds" / "policies.yaml").read_text())
    assert len(policies) == 15
    assert len({p["id"] for p in policies}) == 15
