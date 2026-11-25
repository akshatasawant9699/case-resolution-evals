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


@pytest.mark.parametrize("path", TASK_FILES, ids=lambda p: p.stem)
def test_task_fixtures_load_and_checks_reference_real_columns(path, tmp_path):
    import sqlite3

    from mcp_servers.db import build_database

    task = yaml.safe_load(path.read_text())
    db = build_database(tmp_path / "t.sqlite", task.get("fixtures"))
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT 1 FROM customers WHERE id = ?", (task["context"]["customer_id"],)).fetchone()
        assert conn.execute("SELECT 1 FROM cases WHERE id = ?", (task["context"]["case_id"],)).fetchone()
        for check in task["expected_state"]:
            columns = {row[1] for row in conn.execute(f"PRAGMA table_info({check['table']})")}
            referenced = set(check["where"]) | ({check["field"]} if "field" in check else set())
            assert referenced <= columns, f"unknown columns {referenced - columns} in {check['table']}"


def test_task_ids_are_unique():
    ids = [yaml.safe_load(p.read_text())["id"] for p in TASK_FILES]
    assert len(ids) == len(set(ids))
