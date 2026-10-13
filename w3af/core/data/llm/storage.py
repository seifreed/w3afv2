"""SQLite storage for LLM verification records."""

import json
from typing import Any


class VerificationStorage:
    """Store bounded JSON results without changing KB pickles."""

    TABLE = "llm_verifications"

    def __init__(self, database):
        self.database = database
        if not database.table_exists(self.TABLE):
            database.create_table(
                self.TABLE,
                [
                    ("finding_uniq_id", "TEXT PRIMARY KEY"),
                    ("status", "TEXT NOT NULL"),
                    ("provider", "TEXT"),
                    ("model", "TEXT"),
                    ("result", "TEXT"),
                    ("error", "TEXT"),
                ],
            )

    def create_pending(self, finding_uniq_id: str) -> bool:
        existing = self.get(finding_uniq_id)
        if existing and existing["status"] in {
            "pending",
            "running",
            "confirmed",
            "not_confirmed",
        }:
            return False
        self.database.execute(
            f"INSERT OR REPLACE INTO {self.TABLE} VALUES (?, ?, ?, ?, ?, ?)",
            (finding_uniq_id, "pending", None, None, None, None),
            commit=True,
        )
        return True

    def update(self, finding_uniq_id: str, status: str, **values: Any) -> None:
        self.database.execute(
            f"UPDATE {self.TABLE} SET status=?, provider=?, model=?, result=?, error=? "
            "WHERE finding_uniq_id=?",
            (
                status,
                values.get("provider"),
                values.get("model"),
                (
                    json.dumps(values["result"])
                    if values.get("result") is not None
                    else None
                ),
                values.get("error"),
                finding_uniq_id,
            ),
            commit=True,
        )

    def get(self, finding_uniq_id: str) -> dict[str, Any] | None:
        row = self.database.select_one(
            f"SELECT finding_uniq_id, status, provider, model, result, error "
            f"FROM {self.TABLE} WHERE finding_uniq_id=?",
            (finding_uniq_id,),
        )
        if row is None:
            return None
        return {
            "finding_uniq_id": row[0],
            "status": row[1],
            "provider": row[2],
            "model": row[3],
            "result": json.loads(row[4]) if row[4] else None,
            "error": row[5],
        }
