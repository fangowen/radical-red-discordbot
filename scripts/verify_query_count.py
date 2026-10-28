"""Compare lazy/eager encounter queries without changing the configured database.

Run from the project root: python3 -m scripts.verify_query_count
"""

import ast
import inspect
import json
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine, event, func
from sqlalchemy.orm import sessionmaker

from api import main as api
from db.base import Base
from db.models import TrainerEncounter, TrainerPokemon
from scripts import seed_db


class RemoveEagerLoading(ast.NodeTransformer):
    def visit_Call(self, node):
        node = self.generic_visit(node)
        if isinstance(node.func, ast.Attribute) and node.func.attr == "options":
            return node.func.value
        return node


def lazy_endpoint():
    # Reuse the real serialization logic, removing only the loading options.
    tree = ast.parse(inspect.getsource(api.get_encounter))
    tree.body[0].decorator_list = []
    tree = ast.fix_missing_locations(RemoveEagerLoading().visit(tree))
    namespace = dict(api.__dict__)
    namespace.update(get_cache=lambda key: None, set_cache=lambda *args: None)
    exec(compile(tree, "<lazy encounter baseline>", "exec"), namespace)
    return namespace["get_encounter"]


def measure(engine, sessions, endpoint, encounter_id):
    statements = []

    def record(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    # A fresh session prevents its identity map from hiding lazy queries.
    with sessions() as db:
        event.listen(engine, "before_cursor_execute", record)
        try:
            with patch.object(api, "get_cache", return_value=None), patch.object(
                api, "set_cache"
            ):
                payload = endpoint(encounter_id, db=db)
                json.dumps(payload)
        finally:
            event.remove(engine, "before_cursor_execute", record)
    return len(statements), payload


def main():
    if not Path("data/parsed_encounters.json").is_file():
        raise RuntimeError("Run this command from the project root")

    engine = create_engine("sqlite:///:memory:")
    sessions = sessionmaker(bind=engine)
    try:
        Base.metadata.create_all(engine)
        with patch.object(seed_db, "SessionLocal", sessions):
            seed_db.seed()

        with sessions() as db:
            encounter_ids = [
                row[0]
                for row in db.query(TrainerPokemon.encounter_id)
                .group_by(TrainerPokemon.encounter_id)
                .having(func.count(TrainerPokemon.id) == 6)
                .having(func.count(func.distinct(TrainerPokemon.pokemon_id)) == 6)
                .order_by(TrainerPokemon.encounter_id)
                .all()
            ]
        if not encounter_ids:
            raise RuntimeError("No encounter with six distinct Pokemon found")

        baseline = lazy_endpoint()
        for encounter_id in encounter_ids:
            lazy_count, lazy_data = measure(engine, sessions, baseline, encounter_id)
            eager_count, eager_data = measure(
                engine, sessions, api.get_encounter, encounter_id
            )
            # Team order is unspecified by the schema; compare independently.
            canonical = lambda data: dict(
                data, team=sorted(data["team"], key=lambda mon: mon["pokemon"])
            )
            if canonical(lazy_data) != canonical(eager_data):
                raise AssertionError("Lazy and eager responses differ")
            if (lazy_count, eager_count) != (14, 1):
                raise AssertionError(
                    f"Encounter {encounter_id}: lazy={lazy_count}, eager={eager_count}"
                )

        with sessions() as db:
            sample = db.get(TrainerEncounter, encounter_ids[0])
            print(f"Example: {sample.location} (encounter {sample.id})")
        print(f"Verified {len(encounter_ids)} encounters with six distinct Pokemon")
        print("Each full response: lazy=14 SQL statements; eager=1 SQL statement")
        print("Responses match; Redis bypassed; fresh session for each lookup")
        print("SQLite snapshot only; no production latency measurement")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
