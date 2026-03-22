# modules/sql/engine.py
import sqlite3
import pandas as pd

def create_db(tables):
    conn = sqlite3.connect(":memory:")
    for t, rows in tables.items():
        pd.DataFrame(rows).to_sql(t, conn, index=False)
    return conn

def run_query(conn, query):
    try:
        return pd.read_sql(query, conn), None
    except Exception as e:
        return None, str(e)