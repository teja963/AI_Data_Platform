# modules/sql/engine.py
import importlib.util
import os
import sqlite3
import sys
from functools import lru_cache

import pandas as pd


def create_db(tables):
    conn = sqlite3.connect(":memory:")
    for table_name, rows in tables.items():
        pd.DataFrame(rows).to_sql(table_name, conn, index=False)
    return conn


def run_query(conn, query):
    try:
        return pd.read_sql(query, conn), None
    except Exception as e:
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
