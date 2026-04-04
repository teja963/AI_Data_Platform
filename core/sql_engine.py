import duckdb


def run_query(query):
    conn = duckdb.connect()
    try:
        result = conn.execute(query).fetchdf()
        return result
    except Exception as e:
        return str(e)
