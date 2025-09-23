import duckdb
import pandas as pd

from src.compiler.schema import HashingCfg
from src.connectors.csv_local import CsvLocalConnector
from src.connectors.postgres import PostgresConnector


def _compute_hashes(expr: str, df: pd.DataFrame) -> list[str]:
    con = duckdb.connect()
    try:
        con.execute("INSTALL digest; LOAD digest;")
    except Exception:
        import hashlib

        def _md5(value):
            data = "" if value is None else str(value)
            return hashlib.md5(data.encode("utf-8")).hexdigest()

        con.create_function("md5", _md5, return_type=str)
    con.register("sample_df", df)
    rows = con.execute(f"SELECT {expr} AS h FROM sample_df ORDER BY h").fetchall()
    return [row[0] for row in rows]


def test_double_md5_parity_between_postgres_and_duckdb():
    df = pd.DataFrame(
        [
            {"id": 1, "name": "Alice", "amount": 10.5},
            {"id": 2, "name": "Bob", "amount": None},
            {"id": 3, "name": "ALICE", "amount": 7.1},
        ]
    )

    hashing = HashingCfg(
        algorithm="double_md5", delimiter="|", null_token="<NULL>", case="lower"
    )
    pg = PostgresConnector("postgresql+psycopg2://user:pass@localhost/db")
    csv = CsvLocalConnector("csv://")

    expr_pg = pg.hash_expr(["id", "name", "amount"], hashing)
    expr_csv = csv.hash_expr(["id", "name", "amount"], hashing)

    hashes_pg = _compute_hashes(expr_pg, df)
    hashes_csv = _compute_hashes(expr_csv, df)

    assert hashes_pg == hashes_csv


def test_md5_row_parity_between_postgres_and_duckdb():
    df = pd.DataFrame(
        [
            {"id": 1, "name": "Alice", "amount": 10.5},
            {"id": 2, "name": "Bob", "amount": 5.0},
        ]
    )

    hashing = HashingCfg(
        algorithm="md5_row", delimiter=",", null_token="NULL", case="none"
    )
    pg = PostgresConnector("postgresql+psycopg2://user:pass@localhost/db")
    csv = CsvLocalConnector("csv://")

    expr_pg = pg.hash_expr(["id", "name", "amount"], hashing)
    expr_csv = csv.hash_expr(["id", "name", "amount"], hashing)

    hashes_pg = _compute_hashes(expr_pg, df)
    hashes_csv = _compute_hashes(expr_csv, df)

    assert hashes_pg == hashes_csv
