"""SQL persistence for history metadata."""

from w3af.core.data.db.exceptions import DBException
from w3af.core.data.db.sql_identifier import require_safe_identifier

SELECT_ALL = "SELECT * FROM %s"
SELECT_BY_ID = "SELECT * FROM %s WHERE id = ? "
INSERT_HISTORY = (
    "INSERT INTO %s "
    "(id, url, code, tag, mark, info, time, msg, content_type, "
    "charset, method, response_size, codef, alias, has_qs) "
    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)"
)


class HistoryRepository:
    """Store and retrieve history rows without knowing their domain object."""

    def __init__(self, db, table_name, columns, primary_key_columns, index_columns):
        self._db = db
        self._table_name = require_safe_identifier(table_name)
        self._columns = columns
        self._primary_key_columns = primary_key_columns
        self._index_columns = index_columns

    def init(self) -> None:
        if self._db.table_exists(self._table_name):
            return

        self._db.create_table(
            self._table_name, self._columns, self._primary_key_columns
        ).result()
        self._db.create_index(self._table_name, self._index_columns).result()

    def find(self, search_data):
        sql = SELECT_ALL % self._table_name
        conditions = [
            f"{require_safe_identifier(column)} {operator} ?"
            for column, _, operator in search_data
        ]
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)

        values = [value for _, value, _ in search_data]

        try:
            return self._db.select(sql, values)
        except DBException as error:
            raise DBException(
                "You performed an invalid search. Please verify your syntax."
            ) from error

    def load(self, item_id, retry=True):
        sql = SELECT_BY_ID % self._table_name
        try:
            row = self._db.select_one(sql, (item_id,))
        except DBException as error:
            msg = (
                'An unexpected error occurred while searching for id "%s"'
                ' in table "%s". Original exception: "%s".'
            )
            raise DBException(msg % (item_id, self._table_name, error)) from error

        if row is not None:
            return row

        if not retry:
            msg = (
                'An internal error occurred while searching for id "%s",'
                " even after commit/retry"
            )
            raise DBException(msg % item_id)

        self._db.commit()
        return self.load(item_id, retry=False)

    def insert(self, values) -> None:
        sql = INSERT_HISTORY % self._table_name
        self._db.execute(sql, values)

    def clear(self) -> None:
        if self._db.table_exists(self._table_name):
            self._db.clear_table(self._table_name).result()
