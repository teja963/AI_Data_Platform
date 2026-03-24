# modules/sql/engine.py
import datetime as dt
import importlib.util
import os
import re
import sqlite3
import sys
from functools import lru_cache

import pandas as pd


MYSQL_TO_PYTHON_STRFTIME = {
    "%i": "%M",
    "%s": "%S",
}


def _parse_datetime(value):
    if value is None or value == "":
        return None

    if isinstance(value, dt.datetime):
        return value

    if isinstance(value, dt.date):
        return dt.datetime.combine(value, dt.time.min)

    value = str(value).strip()
    for fmt in (
        "%Y-%m-%d",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%f",
    ):
        try:
            return dt.datetime.strptime(value, fmt)
        except ValueError:
            continue

    return None


def _parse_date(value):
    parsed = _parse_datetime(value)
    return parsed.date() if parsed else None


def _mysql_datediff(end_date, start_date):
    end_value = _parse_date(end_date)
    start_value = _parse_date(start_date)

    if end_value is None or start_value is None:
        return None

    return (end_value - start_value).days


def _mysql_curdate():
    return dt.date.today().isoformat()


def _mysql_year(value):
    parsed = _parse_date(value)
    return parsed.year if parsed else None


def _mysql_month(value):
    parsed = _parse_date(value)
    return parsed.month if parsed else None


def _mysql_day(value):
    parsed = _parse_date(value)
    return parsed.day if parsed else None


def _mysql_date_format(value, fmt):
    parsed = _parse_date(value)
    if parsed is None or fmt is None:
        return None

    python_format = str(fmt)
    for mysql_token, python_token in MYSQL_TO_PYTHON_STRFTIME.items():
        python_format = python_format.replace(mysql_token, python_token)

    return parsed.strftime(python_format)


def _mysql_timestampdiff(unit, start_value, end_value):
    start_dt = _parse_datetime(start_value)
    end_dt = _parse_datetime(end_value)

    if start_dt is None or end_dt is None or unit is None:
        return None

    delta = end_dt - start_dt
    unit_name = str(unit).strip().upper()
    total_seconds = int(delta.total_seconds())

    if unit_name == "SECOND":
        return total_seconds
    if unit_name == "MINUTE":
        return total_seconds // 60
    if unit_name == "HOUR":
        return total_seconds // 3600
    if unit_name == "DAY":
        return delta.days
    if unit_name == "WEEK":
        return delta.days // 7
    if unit_name == "MONTH":
        return (end_dt.year - start_dt.year) * 12 + (end_dt.month - start_dt.month)
    if unit_name == "YEAR":
        return end_dt.year - start_dt.year - (
            (end_dt.month, end_dt.day) < (start_dt.month, start_dt.day)
        )

    return None


def _register_mysql_compat_functions(conn):
    conn.create_function("DATEDIFF", 2, _mysql_datediff)
    conn.create_function("CURDATE", 0, _mysql_curdate)
    conn.create_function("YEAR", 1, _mysql_year)
    conn.create_function("MONTH", 1, _mysql_month)
    conn.create_function("DAY", 1, _mysql_day)
    conn.create_function("DAYOFMONTH", 1, _mysql_day)
    conn.create_function("DATE_FORMAT", 2, _mysql_date_format)
    conn.create_function("TIMESTAMPDIFF", 3, _mysql_timestampdiff)


def _translate_mysql_interval_expression(query, function_name, sign):
    pattern = re.compile(
        rf"{function_name}\s*\(\s*(?P<expr>.+?)\s*,\s*INTERVAL\s+(?P<value>-?\d+)\s+(?P<unit>DAY|MONTH|YEAR)\s*\)",
        flags=re.IGNORECASE | re.DOTALL,
    )

    def replace(match):
        expr = match.group("expr").strip()
        raw_value = int(match.group("value"))
        unit = match.group("unit").lower()
        adjusted_value = raw_value if sign == "+" else -raw_value
        modifier_sign = "+" if adjusted_value >= 0 else "-"
        modifier = f"{modifier_sign}{abs(adjusted_value)} {unit.lower()}"
        return f"date({expr}, '{modifier}')"

    return pattern.sub(replace, query)


def _translate_mysql_timestampdiff(query):
    pattern = re.compile(
        r"TIMESTAMPDIFF\s*\(\s*(?P<unit>SECOND|MINUTE|HOUR|DAY|WEEK|MONTH|YEAR)\s*,",
        flags=re.IGNORECASE,
    )
    return pattern.sub(lambda match: f"TIMESTAMPDIFF('{match.group('unit').upper()}',", query)


def translate_mysql_to_sqlite(query):
    translated = query
    translated = _translate_mysql_interval_expression(translated, "DATE_ADD", "+")
    translated = _translate_mysql_interval_expression(translated, "DATE_SUB", "-")
    translated = _translate_mysql_timestampdiff(translated)
    translated = re.sub(r"\bNOW\s*\(\s*\)", "CURRENT_TIMESTAMP", translated, flags=re.IGNORECASE)
    return translated


def create_db(tables):
    conn = sqlite3.connect(":memory:")
    _register_mysql_compat_functions(conn)
    for table_name, rows in tables.items():
        pd.DataFrame(rows).to_sql(table_name, conn, index=False)
    return conn


UNSUPPORTED_SQL_FEATURE_HINTS = {
    r"\bMERGE\b": (
        "The local SQL runner does not support native MERGE statements yet. "
        "Use this syntax as a concept reference, but execute merge-style logic outside the local SQLite runner."
    ),
    r"\bPIVOT\b": (
        "Native PIVOT is not available in the local SQL runner. "
        "Use CASE-based conditional aggregation when you want a runnable local equivalent."
    ),
    r"\bROLLUP\b|\bGROUPING SETS\b|\bCUBE\b": (
        "ROLLUP, CUBE, and GROUPING SETS are not supported by the local SQL runner. "
        "Use UNION ALL subtotal queries locally if you need an executable fallback."
    ),
}


def _get_sql_error_hint(query):
    for pattern, hint in UNSUPPORTED_SQL_FEATURE_HINTS.items():
        if re.search(pattern, query, flags=re.IGNORECASE):
            return hint

    return None


def run_query(conn, query):
    try:
        translated_query = translate_mysql_to_sqlite(query)
        return pd.read_sql(translated_query, conn), None
    except Exception as e:
        hint = _get_sql_error_hint(query)
        if hint:
            return None, f"{e}\n\nHint: {hint}"
        return None, str(e)


def is_pyspark_available():
    return importlib.util.find_spec("pyspark") is not None


@lru_cache(maxsize=1)
def get_spark_session():
    if not is_pyspark_available():
        raise ModuleNotFoundError(
            "PySpark is not installed in the current interpreter."
        )

    from pyspark.sql import SparkSession

    os.environ["PYSPARK_PYTHON"] = sys.executable
    os.environ["PYSPARK_DRIVER_PYTHON"] = sys.executable

    spark = (
        SparkSession.builder
        .master("local[*]")
        .appName("AI_Data_Engg")
        .config("spark.ui.enabled", "false")
        .config("spark.sql.shuffle.partitions", "4")
        .config("spark.pyspark.python", sys.executable)
        .config("spark.pyspark.driver.python", sys.executable)
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("ERROR")
    return spark


def create_spark_tables(tables):
    spark = get_spark_session()
    table_dfs = {}

    for table_name, rows in tables.items():
        pdf = pd.DataFrame(rows)
        table_dfs[table_name] = spark.createDataFrame(pdf)

    return table_dfs


def _extract_result_dataframe(namespace, table_names):
    from pyspark.sql import DataFrame as SparkDataFrame

    result = namespace.get("result")
    if isinstance(result, SparkDataFrame):
        return result

    dataframe_candidates = [
        value
        for name, value in namespace.items()
        if name not in table_names and isinstance(value, SparkDataFrame)
    ]

    if dataframe_candidates:
        return dataframe_candidates[-1]

    return None


def run_pyspark_code(tables, code):
    try:
        spark = get_spark_session()
        table_dfs = create_spark_tables(tables)
        namespace = {
            "__builtins__": __builtins__,
            "spark": spark,
            **table_dfs,
        }

        exec(code, namespace, namespace)

        result_df = _extract_result_dataframe(namespace, set(table_dfs.keys()))
        if result_df is None:
            return None, (
                "PySpark code must create a DataFrame. "
                "Assign the final result to `result` or keep your final DataFrame in a variable."
            )

        return result_df.toPandas(), None
    except Exception as e:
        return None, str(e)
