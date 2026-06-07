import streamlit as st


SQL_CONCEPT_SECTIONS = [
    {
        "title": "Core Query Skeleton",
        "concept": "The standard order of thought when writing a SQL query from raw rows to final answer.",
        "keywords": "SELECT, FROM, WHERE, GROUP BY, HAVING, ORDER BY, LIMIT",
        "syntax": """SELECT <column_or_expression> AS <alias>, ...
FROM <table_name>
WHERE <row_level_condition>
GROUP BY <grouping_column>, ...
HAVING <aggregate_condition>
ORDER BY <column_or_alias> [ASC|DESC]
LIMIT <n>;""",
        "tip": "Think in this order: source rows -> row filter -> grouping -> aggregate filter -> final projection -> sorting -> limiting.",
    },
    {
        "title": "Join Syntax",
        "concept": "Combine rows from multiple tables based on a relationship.",
        "keywords": "JOIN, LEFT JOIN, RIGHT JOIN, FULL JOIN, CROSS JOIN, SELF JOIN, ON",
        "syntax": """SELECT ...
FROM <left_table> AS l
JOIN <right_table> AS r
  ON l.<key> = r.<key>;

SELECT ...
FROM <left_table> AS l
LEFT JOIN <right_table> AS r
  ON l.<key> = r.<key>;

SELECT ...
FROM <left_table> AS l
CROSS JOIN <right_table> AS r;

SELECT ...
FROM <table_name> AS a
JOIN <table_name> AS b
  ON a.<key> = b.<related_key>;""",
        "tip": "Put table-specific filters carefully. A WHERE filter on the right side after a LEFT JOIN can collapse it into INNER JOIN behavior.",
    },
    {
        "title": "Aggregation And HAVING",
        "concept": "Collapse many rows into grouped summaries.",
        "keywords": "COUNT, SUM, AVG, MIN, MAX, COUNT(DISTINCT ...), GROUP BY, HAVING",
        "syntax": """SELECT
    <group_col>,
    COUNT(*) AS row_count,
    COUNT(DISTINCT <col>) AS unique_count,
    SUM(<metric_col>) AS total_metric,
    AVG(<metric_col>) AS avg_metric,
    MIN(<metric_col>) AS min_metric,
    MAX(<metric_col>) AS max_metric
FROM <table_name>
GROUP BY <group_col>
HAVING <aggregate_expression> <operator> <value>;""",
        "tip": "Use WHERE for row-level filters before grouping. Use HAVING for aggregate-level filters after grouping.",
    },
    {
        "title": "Conditional Logic And NULL Handling",
        "concept": "Build rule-based columns and safely handle missing values.",
        "keywords": "CASE WHEN, COALESCE, IFNULL, NULLIF, IS NULL, IS NOT NULL",
        "syntax": """CASE
    WHEN <condition_1> THEN <value_1>
    WHEN <condition_2> THEN <value_2>
    ELSE <fallback_value>
END

COALESCE(<expr_1>, <expr_2>, <fallback>)
IFNULL(<expr>, <fallback>)
NULLIF(<expr_1>, <expr_2>)

<column> IS NULL
<column> IS NOT NULL""",
        "tip": "CASE is branching logic. COALESCE and IFNULL are replacement logic. Never compare NULL with = or !=",
    },
    {
        "title": "Subqueries, CTEs, EXISTS",
        "concept": "Break complex logic into smaller query blocks or test the existence of related rows.",
        "keywords": "WITH, EXISTS, NOT EXISTS, IN, scalar subquery, correlated subquery",
        "syntax": """WITH <cte_name> AS (
    SELECT ...
    FROM ...
)
SELECT ...
FROM <cte_name>;

SELECT ...
FROM <table_name> AS t
WHERE EXISTS (
    SELECT 1
    FROM <related_table> AS r
    WHERE r.<key> = t.<key>
);

SELECT ...
FROM <table_name>
WHERE <column> IN (
    SELECT <column>
    FROM <other_table>
);""",
        "tip": "Use CTEs for readability. Use EXISTS and NOT EXISTS when the question is about presence or absence of related rows rather than returning the related rows themselves.",
    },
    {
        "title": "Window Functions",
        "concept": "Compute per-row analytics while still keeping row-level detail.",
        "keywords": "OVER, PARTITION BY, ORDER BY, ROW_NUMBER, RANK, DENSE_RANK, LAG, LEAD, ROWS BETWEEN, RANGE BETWEEN",
        "syntax": """<window_function>() OVER (
    PARTITION BY <partition_col>, ...
    ORDER BY <sort_col> [ASC|DESC], ...
)

ROW_NUMBER() OVER (...)
RANK() OVER (...)
DENSE_RANK() OVER (...)
LAG(<col>, <offset>, <default>) OVER (...)
LEAD(<col>, <offset>, <default>) OVER (...)

SUM(<metric_col>) OVER (
    PARTITION BY <partition_col>
    ORDER BY <sort_col>
    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
)

AVG(<metric_col>) OVER (
    ORDER BY <sort_col>
    ROWS BETWEEN <n> PRECEDING AND CURRENT ROW
)""",
        "tip": "PARTITION BY defines the group. ORDER BY defines row sequence. Frame clauses define cumulative or rolling scope.",
    },
    {
        "title": "String, Date, And Type Conversion",
        "concept": "Transform text, compute date intervals, format date parts, and cast values between types.",
        "keywords": "CONCAT, SUBSTRING, TRIM, LOWER, UPPER, CAST, CONVERT, DATEDIFF, DATE_ADD, DATE_SUB, DATE_FORMAT, YEAR, MONTH, DAY, CURDATE",
        "syntax": """CONCAT(<expr_1>, <expr_2>, ...)
SUBSTRING(<string_expr>, <start_pos>, <length>)
TRIM(<string_expr>)
LOWER(<string_expr>)
UPPER(<string_expr>)

CAST(<expr> AS <type_name>)
CONVERT(<expr>, <type_name>)

DATEDIFF(<end_date>, <start_date>)
DATE_ADD(<date_expr>, INTERVAL <n> DAY)
DATE_SUB(<date_expr>, INTERVAL <n> DAY)
DATE_FORMAT(<date_expr>, '%Y-%m')
YEAR(<date_expr>)
MONTH(<date_expr>)
DAY(<date_expr>)
CURDATE()""",
        "tip": "If text and date logic mix in the same query, cast first, then compare or format. Do not assume every string behaves like a date.",
    },
    {
        "title": "Set Operations And Deduplication",
        "concept": "Combine compatible result sets or remove duplicate rows.",
        "keywords": "UNION, UNION ALL, DISTINCT, EXCEPT, INTERSECT",
        "syntax": """SELECT <col_1>, <col_2>, ...
FROM <table_a>

UNION

SELECT <col_1>, <col_2>, ...
FROM <table_b>;

SELECT DISTINCT <col_1>, <col_2>
FROM <table_name>;""",
        "tip": "UNION removes duplicates. UNION ALL keeps all rows. DISTINCT is often the cleanest answer when you only need unique row combinations.",
    },
    {
        "title": "Ranking, Top-N, Pagination",
        "concept": "Retrieve the highest, lowest, or Nth rows with or without ties.",
        "keywords": "ORDER BY, LIMIT, OFFSET, ROW_NUMBER, RANK, DENSE_RANK",
        "syntax": """SELECT ...
FROM <table_name>
ORDER BY <metric_col> DESC
LIMIT <n>;

SELECT *
FROM (
    SELECT
        ...,
        ROW_NUMBER() OVER (
            PARTITION BY <group_col>
            ORDER BY <metric_col> DESC
        ) AS rn
    FROM <table_name>
) AS ranked
WHERE rn <= <n>;""",
        "tip": "Use ROW_NUMBER when you must pick exactly one row. Use DENSE_RANK when ties should stay together.",
    },
    {
        "title": "Recursive CTEs, Pivot, Rollup, JSON",
        "concept": "Handle hierarchies, subtotal-style summaries, cross-tab output, and semi-structured values.",
        "keywords": "WITH RECURSIVE, PIVOT, CASE-based pivot, ROLLUP, CUBE, GROUPING SETS, JSON_EXTRACT, JSON_VALUE, JSON_OBJECT",
        "syntax": """WITH RECURSIVE <cte_name> AS (
    SELECT <base_cols>
    FROM <base_table>
    WHERE <base_condition>

    UNION ALL

    SELECT <recursive_cols>
    FROM <source_table> AS s
    JOIN <cte_name> AS c
      ON s.<parent_key> = c.<child_key>
)
SELECT ...
FROM <cte_name>;

SELECT
    <group_col>,
    SUM(CASE WHEN <pivot_col> = '<value_1>' THEN <metric_col> END) AS <value_1_alias>,
    SUM(CASE WHEN <pivot_col> = '<value_2>' THEN <metric_col> END) AS <value_2_alias>
FROM <table_name>
GROUP BY <group_col>;

SELECT
    <group_col_1>,
    <group_col_2>,
    SUM(<metric_col>) AS total_metric
FROM <table_name>
GROUP BY ROLLUP(<group_col_1>, <group_col_2>);

JSON_EXTRACT(<json_col>, '$.<path>')
JSON_VALUE(<json_col>, '$.<path>')
JSON_OBJECT('<key_1>', <expr_1>, '<key_2>', <expr_2>)""",
        "tip": "Use recursive CTEs for parent-child traversal, ROLLUP or GROUPING SETS for subtotal layers, and CASE-based pivoting when native PIVOT is unavailable.",
    },
    {
        "title": "Data Engineering Patterns",
        "concept": "Apply warehouse-style write logic, deduplication rules, and quality checks at the right grain.",
        "keywords": "MERGE, UPSERT, SCD Type 1, SCD Type 2, deduplication, surrogate key, business key, data quality",
        "syntax": """MERGE INTO <target_table> AS t
USING <source_table> AS s
  ON t.<business_key> = s.<business_key>
WHEN MATCHED THEN
  UPDATE SET
    t.<col_1> = s.<col_1>,
    t.<updated_at> = s.<updated_at>
WHEN NOT MATCHED THEN
  INSERT (<col_1>, <col_2>, ...)
  VALUES (s.<col_1>, s.<col_2>, ...);

UPDATE <dimension_table>
SET
    <current_flag_col> = 0,
    <end_date_col> = <effective_date_expr>
WHERE <business_key_col> = <incoming_business_key>
  AND <current_flag_col> = 1;

SELECT COUNT(*) - COUNT(DISTINCT <business_key_col>) AS duplicate_count
FROM <table_name>;

SELECT SUM(CASE WHEN <critical_col> IS NULL THEN 1 ELSE 0 END) AS null_violations
FROM <table_name>;""",
        "tip": "Always identify the grain first. Most warehouse bugs come from mismatched grain, non-idempotent merge logic, or missing quality checks before writes.",
    },
    {
        "title": "Analytics Metrics And Product Patterns",
        "concept": "Build reusable syntax for retention, funnels, cohorts, YoY growth, sessionization, and activity metrics.",
        "keywords": "retention, cohort, funnel, DATEDIFF, TIMESTAMPDIFF, CASE WHEN, COUNT DISTINCT, DAU, WAU, MAU, YoY, sessionization",
        "syntax": """COUNT(DISTINCT CASE WHEN <event_col> = '<stage_name>' THEN <entity_id> END)

DATEDIFF(<activity_date_col>, <cohort_date_col>)

TIMESTAMPDIFF(
    MINUTE,
    LAG(<timestamp_col>) OVER (
        PARTITION BY <entity_id>
        ORDER BY <timestamp_col>
    ),
    <timestamp_col>
)

SUM(
    CASE
        WHEN <gap_condition> THEN 1
        ELSE 0
    END
) OVER (
    PARTITION BY <entity_id>
    ORDER BY <timestamp_col>
) AS <session_id_alias>

ROUND(
    100.0 * (<current_metric> - <previous_metric>) / NULLIF(<previous_metric>, 0),
    <scale>
) AS <growth_alias>""",
        "tip": "These patterns still come from core SQL blocks: CASE, DISTINCT counts, self-joins or windows, and careful date-gap logic.",
    },
    {
        "title": "Plan, Debug, And Sanity Checks",
        "concept": "Understand how the query is executed and where logic mistakes usually come from.",
        "keywords": "EXPLAIN, intermediate CTEs, row counts, deterministic ordering",
        "syntax": """EXPLAIN
SELECT ...
FROM ...;

WITH step_1 AS (...),
step_2 AS (...)
SELECT *
FROM step_2
ORDER BY <stable_key>;""",
        "tip": "If an answer looks right but validates wrong, check duplicates, join grain, NULL handling, and whether you grouped at the right level.",
    },
]


PYSPARK_CONCEPT_SECTIONS = [
    {
        "title": "Spark Session, Entry Points, And DataFrame Creation",
        "concept": "Start from SparkSession, create DataFrames explicitly, and think in schemas from the beginning.",
        "keywords": "SparkSession, createDataFrame, range, schema, Row, toDF",
        "syntax": """from pyspark.sql import SparkSession
from pyspark.sql.functions import *
from pyspark.sql.window import Window

spark = SparkSession.builder.appName("<app_name>").getOrCreate()

spark.createDataFrame(<python_rows>, schema=<schema>)
spark.range(<start>, <end>, <step>)
<rdd>.toDF(["<col_1>", "<col_2>"])""",
        "tip": "In PySpark, the real starting point is usually SparkSession plus a schema-aware DataFrame, not a single query string.",
    },
    {
        "title": "Read APIs And Input Sources",
        "concept": "Load batch or streaming data with explicit formats, options, and schemas.",
        "keywords": "spark.read, spark.readStream, format, option, options, schema, load, csv, parquet, json",
        "syntax": """spark.read.format("<format_name>") \\
    .option("<option_key>", "<option_value>") \\
    .schema(<schema>) \\
    .load("<input_path>")

spark.read.csv("<input_path>", header=True, inferSchema=False)
spark.read.parquet("<input_path>")
spark.read.json("<input_path>")

spark.readStream.format("<stream_format>") \\
    .option("<option_key>", "<option_value>") \\
    .schema(<schema>) \\
    .load("<input_path>")""",
        "tip": "Prefer explicit schemas in interviews and production-like code. It makes type behavior predictable.",
    },
    {
        "title": "Transformation Pipeline",
        "concept": "The typical DataFrame pipeline from source to final result.",
        "keywords": "select, filter, withColumn, groupBy, agg, orderBy, limit",
        "syntax": """from pyspark.sql.functions import *
from pyspark.sql.window import Window

result = (
    <df>
    .filter(<row_condition>)
    .withColumn("<new_col>", <expression>)
    .groupBy("<group_col>")
    .agg(<aggregation>.alias("<alias>"))
    .filter(<post_aggregation_condition>)
    .orderBy(col("<sort_col>").desc())
    .limit(<n>)
)""",
        "tip": "Think in transformations. Every step returns a new DataFrame.",
    },
    {
        "title": "Column Expressions And Filtering",
        "concept": "Reference columns, create derived columns, and apply row filters.",
        "keywords": "col, lit, alias, filter, where, withColumn, selectExpr",
        "syntax": """col("<column_name>")
lit(<constant_value>)

<df>.select(
    col("<column_name>").alias("<alias_name>"),
    (<expression>).alias("<alias_name>")
)

<df>.withColumn("<new_col>", <expression>)
<df>.filter(<boolean_expression>)
<df>.where(<boolean_expression>)
<df>.selectExpr("<expression> AS <alias_name>")""",
        "tip": "Use col() for columns and lit() for raw constants. Chain expressions instead of mixing Python values and Spark columns incorrectly.",
    },
    {
        "title": "Join Syntax",
        "concept": "Join DataFrames with explicit conditions and join types.",
        "keywords": "join, inner, left, right, full, left_semi, left_anti, alias",
        "syntax": """<left_df>.alias("l").join(
    <right_df>.alias("r"),
    col("l.<key>") == col("r.<key>"),
    "inner"
)

<left_df>.alias("l").join(
    <right_df>.alias("r"),
    (col("l.<key>") == col("r.<key>")) & (<extra_condition>),
    "left"
)

<left_df>.join(<right_df>, <condition>, "left_anti")""",
        "tip": "Always be explicit about aliases and join type. It prevents ambiguous-column mistakes.",
    },
    {
        "title": "Aggregation And Post-Aggregation Filtering",
        "concept": "Group records, compute summaries, then filter those grouped results.",
        "keywords": "groupBy, agg, sum, avg, count, countDistinct, pivot, rollup, cube, filter after agg",
        "syntax": """<df>.groupBy("<group_col>").agg(
    sum("<value_col>").alias("<sum_alias>"),
    avg("<value_col>").alias("<avg_alias>"),
    count(lit(1)).alias("<count_alias>"),
    countDistinct("<distinct_col>").alias("<distinct_alias>")
)

<df>.groupBy("<group_col>").pivot("<pivot_col>").agg(sum("<value_col>"))
<df>.rollup("<group_col_1>", "<group_col_2>").agg(sum("<value_col>"))
<df>.cube("<group_col_1>", "<group_col_2>").agg(sum("<value_col>"))

<aggregated_df>.filter(col("<aggregate_alias>") > <value>)""",
        "tip": "PySpark does not have a separate HAVING clause. The HAVING idea is a filter after agg(). Pivot, rollup, and cube are still aggregation patterns.",
    },
    {
        "title": "Conditional Logic, NULLs, Strings, And Casting",
        "concept": "Branching logic, NULL-safe operations, string cleanup, and explicit type conversion.",
        "keywords": "when, otherwise, coalesce, isNull, isNotNull, trim, lower, upper, regexp_extract, regexp_replace, split, cast",
        "syntax": """when(<condition>, <value>).otherwise(<fallback>)
coalesce(col("<a>"), col("<b>"), lit(<fallback>))
col("<column_name>").isNull()
col("<column_name>").isNotNull()

trim(col("<string_col>"))
lower(col("<string_col>"))
upper(col("<string_col>"))
regexp_extract(col("<string_col>"), "<pattern>", <group_index>)
regexp_replace(col("<string_col>"), "<pattern>", "<replacement>")
split(col("<string_col>"), "<delimiter>")
col("<column_name>").cast("<type_name>")""",
        "tip": "Use when().otherwise() instead of Python if or else. Spark expressions must stay inside the execution plan.",
    },
    {
        "title": "Window API",
        "concept": "Define partitioning, ordering, and frame boundaries for row-wise analytics.",
        "keywords": "Window.partitionBy, orderBy, rowsBetween, row_number, rank, dense_rank, lag, lead",
        "syntax": """window_spec = Window.partitionBy("<partition_col>").orderBy(col("<sort_col>").desc())

<df>.withColumn("rn", row_number().over(window_spec))
<df>.withColumn("rnk", rank().over(window_spec))
<df>.withColumn("dense_rnk", dense_rank().over(window_spec))
<df>.withColumn("prev_value", lag("<value_col>").over(window_spec))
<df>.withColumn("next_value", lead("<value_col>").over(window_spec))

running_window = (
    Window.partitionBy("<partition_col>")
    .orderBy(col("<sort_col>"))
    .rowsBetween(Window.unboundedPreceding, Window.currentRow)
)

rolling_window = (
    Window.partitionBy("<partition_col>")
    .orderBy(col("<sort_col>"))
    .rowsBetween(-<n>, Window.currentRow)
)""",
        "tip": "Partition defines the group. Order defines sequence. rowsBetween defines cumulative or rolling scope.",
    },
    {
        "title": "Date And Timestamp Functions",
        "concept": "Convert strings to dates, shift dates, extract parts, and compute date differences.",
        "keywords": "to_date, to_timestamp, datediff, date_add, date_sub, year, month, dayofmonth, date_format",
        "syntax": """to_date(col("<date_col>"))
to_timestamp(col("<timestamp_col>"))
datediff(col("<end_date>"), col("<start_date>"))
date_add(col("<date_col>"), <n>)
date_sub(col("<date_col>"), <n>)
year(col("<date_col>"))
month(col("<date_col>"))
dayofmonth(col("<date_col>"))
date_format(col("<date_col>"), "yyyy-MM")""",
        "tip": "When source columns are strings, convert them with to_date() or to_timestamp() before applying date logic.",
    },
    {
        "title": "Complex Types, JSON, And Higher-Order Functions",
        "concept": "Work with arrays, maps, structs, JSON payloads, and nested transformations without flattening too early.",
        "keywords": "array, map, struct, explode, explode_outer, posexplode, collect_list, collect_set, array_contains, size, element_at, from_json, to_json, transform, filter, aggregate",
        "syntax": """array(col("<a>"), col("<b>"), ...)
create_map(lit("<key_1>"), col("<value_1>"), lit("<key_2>"), col("<value_2>"))
struct(col("<a>").alias("<alias_a>"), col("<b>").alias("<alias_b>"))

<df>.withColumn("<item>", explode(col("<array_col>")))
<df>.withColumn("<item>", explode_outer(col("<array_col>")))
<df>.select("*", posexplode(col("<array_col>")).alias("<pos>", "<item>"))

collect_list("<value_col>")
collect_set("<value_col>")
array_contains(col("<array_col>"), <value>)
size(col("<array_col>"))
element_at(col("<array_col>"), <position>)
element_at(col("<map_col>"), lit("<key_name>"))

from_json(col("<json_col>"), <schema>)
to_json(col("<struct_or_array_col>"))

transform(col("<array_col>"), lambda x: <expression_using_x>)
filter(col("<array_col>"), lambda x: <boolean_expression_using_x>)
aggregate(col("<array_col>"), <start_value>, lambda acc, x: <expression>)""",
        "tip": "explode creates more rows. Higher-order functions let you stay nested when flattening would lose structure.",
    },
    {
        "title": "Write APIs And Streaming Sinks",
        "concept": "Persist batch outputs and configure streaming sinks with modes, partitioning, triggers, and checkpoints.",
        "keywords": "write, writeStream, format, mode, save, saveAsTable, partitionBy, outputMode, trigger, checkpointLocation",
        "syntax": """<df>.write.format("<format_name>") \\
    .mode("<write_mode>") \\
    .partitionBy("<partition_col>") \\
    .save("<output_path>")

<df>.write.saveAsTable("<table_name>")

<streaming_df>.writeStream.format("<sink_name>") \\
    .outputMode("<output_mode>") \\
    .option("checkpointLocation", "<checkpoint_path>") \\
    .trigger(processingTime="<interval>") \\
    .start("<output_path_or_sink>")""",
        "tip": "Batch writes finish and return. Streaming writes start a query and stay active, so checkpointing and output mode matter.",
    },
    {
        "title": "Union, Duplicates, Sorting",
        "concept": "Combine DataFrames, remove duplicates, and create deterministic ordering.",
        "keywords": "union, unionByName, distinct, dropDuplicates, orderBy, sortWithinPartitions",
        "syntax": """<df_a>.union(<df_b>)
<df_a>.unionByName(<df_b>, allowMissingColumns=True)

<df>.distinct()
<df>.dropDuplicates()
<df>.dropDuplicates(["<col_1>", "<col_2>"])

<df>.orderBy(col("<sort_col>").desc(), col("<other_sort_col>").asc())""",
        "tip": "Use unionByName when schemas align by column name instead of column position.",
    },
    {
        "title": "Actions, Persistence, Partitioning, And Execution",
        "concept": "Understand what triggers execution, how to persist results, and how data movement affects performance.",
        "keywords": "show, count, collect, cache, persist, repartition, coalesce, broadcast, explain",
        "syntax": """<df>.show(truncate=False)
<df>.count()
<df>.collect()
<df>.take(<n>)

<df>.cache()
<df>.persist()
<df>.repartition(<num_partitions>, "<partition_col>")
<df>.coalesce(<num_partitions>)

<left_df>.join(broadcast(<small_df>), <join_condition>, "inner")

<df>.explain()
<df>.explain("formatted")""",
        "tip": "Transformations are lazy. Actions trigger execution. repartition usually shuffles, coalesce usually narrows, and broadcast() is for explicitly small-side joins.",
    },
    {
        "title": "RDD Bridge And Low-Level Operations",
        "concept": "Drop to RDDs only when you need partition-level control or lower-level functional patterns.",
        "keywords": "rdd, map, flatMap, mapPartitions, reduceByKey, toDF",
        "syntax": """<df>.rdd
<rdd>.map(lambda row: <new_value>)
<rdd>.flatMap(lambda row: <iterable_result>)
<rdd>.mapPartitions(lambda rows: <iterator_logic>)
<pair_rdd>.reduceByKey(lambda a, b: <combined_value>)
<rdd>.toDF(["<col_1>", "<col_2>"])""",
        "tip": "Stay in the DataFrame API by default. Move to RDDs only when the problem truly needs partition-level or record-wise control beyond DataFrame functions.",
    },
    {
        "title": "Explain, Schema, And Debugging",
        "concept": "Inspect structure, verify logic, and understand execution plans.",
        "keywords": "printSchema, show, explain, cache, checkpoint, intermediate DataFrames",
        "syntax": """<df>.printSchema()
<df>.show(truncate=False)
<df>.explain()
<df>.explain("formatted")

<df>.cache()
<df>.count()

step_1 = <df>...
step_2 = step_1...
step_2.show(truncate=False)""",
        "tip": "If a result looks wrong, debug one intermediate DataFrame at a time instead of staring at the final chain.",
    },
]


PYTHON_CONCEPT_SECTIONS = [
    {
        "title": "Core Script Skeleton And Input Handling",
        "concept": "Start from a small, interview-ready Python script and know how to accept values from function parameters or stdin.",
        "keywords": "def, return, if __name__ == '__main__', input(), split(), map(), print()",
        "syntax": """def solve(<arg_1>, <arg_2>):
    # business logic
    return <result>


if __name__ == "__main__":
    raw = input().strip()
    parts = raw.split()
    values = list(map(int, parts))
    answer = solve(values)
    print(answer)""",
        "tip": "For evaluated coding questions, keep the logic in a function. If raw input is required, parse it in the main block and pass structured values into solve().",
    },
    {
        "title": "Lists, Tuples, Sets, And Dictionaries",
        "concept": "Use the right built-in collection for order, uniqueness, membership checks, or key-value lookups.",
        "keywords": "list, tuple, set, dict, append, pop, get, items, enumerate, in",
        "syntax": """values = [1, 2, 3]
pair = (user_id, total)
unique_values = set(values)
lookup = {"a": 1, "b": 2}

values.append(4)
lookup.get("a", 0)
for key, value in lookup.items():
    ...
for index, value in enumerate(values):
    ...

target in unique_values""",
        "tip": "Lists preserve order, sets give fast membership checks, and dictionaries are the default tool for hashing problems.",
    },
    {
        "title": "List Operations And Mutability",
        "concept": "Lists are ordered and mutable, so they are the default structure for sequences you need to update.",
        "keywords": "append, extend, insert, remove, pop, sort, reverse, slicing, copy, list comprehension",
        "syntax": """nums = [10, 20, 30]

nums.append(40)          # [10, 20, 30, 40]
nums.extend([50, 60])    # [10, 20, 30, 40, 50, 60]
nums.insert(1, 15)       # insert at index
nums.remove(20)          # remove first matching value
last = nums.pop()        # remove from end
first = nums.pop(0)      # remove by index

nums.sort()              # in-place ascending
nums.sort(reverse=True)  # in-place descending
ordered = sorted(nums)   # returns a new list

nums[1:4]                # slicing
nums[::-1]               # reverse copy
clone = nums[:]          # shallow copy

filtered = [x for x in nums if x % 2 == 0]""",
        "tip": "Because lists are mutable, copying matters. `a = b` shares the same list, while slicing or list() creates a new one.",
        "operations": [
            ("append(x)", "Add one item at the end."),
            ("extend(iterable)", "Append multiple items in order."),
            ("insert(i, x)", "Insert at a specific index."),
            ("pop([i])", "Remove and return the last item or the item at index i."),
            ("remove(x)", "Remove the first matching value."),
            ("sort(key=..., reverse=...)", "Sort in place."),
            ("sorted(values)", "Return a new sorted list."),
            ("values[start:stop:step]", "Slice without mutating the original list."),
        ],
    },
    {
        "title": "Tuple Operations And Immutability",
        "concept": "Tuples are ordered like lists but immutable, so they work well for fixed pairs, coordinates, and dictionary keys.",
        "keywords": "tuple, packing, unpacking, count, index, immutable, hashable",
        "syntax": """pair = (user_id, amount)
triple = 1, 2, 3         # tuple packing

a, b, c = triple         # unpacking
head, *tail = triple

single = (5,)            # trailing comma matters
pair.count(user_id)
pair.index(amount)

records = {
    ("us", "prod"): 120,
    ("eu", "prod"): 95,
}""",
        "tip": "Use tuples when the shape is fixed and should not change. That is why they appear often in keys like `(hour, device_id)`.",
        "operations": [
            ("tuple(values)", "Create a tuple from any iterable."),
            ("a, b = pair", "Unpack directly into variables."),
            ("pair.count(x)", "Count occurrences of a value."),
            ("pair.index(x)", "Find the first position of a value."),
            ("(key1, key2)", "Use tuple values as dictionary keys."),
        ],
    },
    {
        "title": "Set Operations And Membership",
        "concept": "Sets remove duplicates and give fast membership checks, which is why they are common in dedupe and lookup problems.",
        "keywords": "set, add, remove, discard, union, intersection, difference, symmetric_difference, membership",
        "syntax": """left = {1, 2, 3}
right = {3, 4, 5}

left.add(4)
left.discard(10)         # safe if value does not exist
left.remove(2)           # raises if missing

left | right             # union
left & right             # intersection
left - right             # difference
left ^ right             # symmetric difference

3 in left
unique_items = set(items)""",
        "tip": "Sets are unordered. If the output must preserve original order, pair a set with a list instead of returning the set directly.",
        "operations": [
            ("set(values)", "Create a unique-value collection."),
            ("value in seen", "O(1)-style membership check in common cases."),
            ("add(x)", "Insert one element."),
            ("discard(x)", "Remove safely without raising if missing."),
            ("remove(x)", "Remove and raise if the value is absent."),
            ("left | right", "Union."),
            ("left & right", "Intersection."),
            ("left - right", "Difference."),
        ],
    },
    {
        "title": "Dictionary Operations And Update Patterns",
        "concept": "Dictionaries are the main interview tool for hashing, grouping, memoization, and frequency counting.",
        "keywords": "get, setdefault, update, pop, keys, values, items, dict comprehension",
        "syntax": """counts = {}
counts["click"] = counts.get("click", 0) + 1

grouped = {}
grouped.setdefault("us", []).append({"id": 1})

record = {"id": 1, "status": "new"}
record.update({"status": "done", "updated_at": "2024-01-01"})
removed = record.pop("status", None)

for key, value in record.items():
    ...

flipped = {value: key for key, value in record.items()}""",
        "tip": "Use `get()` for safe reads, `setdefault()` for grouped lists, and remember that duplicate keys overwrite older values unless you design around it.",
        "operations": [
            ("lookup[key]", "Read a required key; raises if missing."),
            ("lookup.get(key, default)", "Read safely with a fallback."),
            ("setdefault(key, [])", "Initialize grouped collections in one step."),
            ("update({...})", "Merge new values into an existing dict."),
            ("pop(key, default)", "Remove and return a value safely."),
            ("keys()", "Iterate over keys."),
            ("values()", "Iterate over values."),
            ("items()", "Iterate over key-value pairs."),
        ],
    },
    {
        "title": "String Operations And Type Conversion",
        "concept": "String handling shows up everywhere in coding rounds: parsing, cleanup, normalization, tokenization, and formatting.",
        "keywords": "strip, split, join, replace, find, startswith, endswith, lower, upper, title, isdigit, int, float, str",
        "syntax": """text = "  Order-101 | ERROR  "

clean = text.strip()
parts = clean.split("|")
joined = "-".join(["a", "b", "c"])

clean.lower()
clean.upper()
clean.replace("ERROR", "FAILED")
clean.startswith("Order")
clean.endswith("ERROR")
clean.find("101")

"123".isdigit()
num = int("123")
price = float("19.95")
label = str(404)

f"order={num}, price={price}" """,
        "tip": "Do cleanup before conversion. In interviews, parsing bugs usually come from splitting too early or casting before trimming.",
        "operations": [
            ("strip()", "Remove leading and trailing whitespace."),
            ("split(sep, maxsplit)", "Tokenize a string."),
            ("join(values)", "Combine many strings with one separator."),
            ("replace(old, new)", "Swap substrings."),
            ("startswith(prefix)", "Check a prefix quickly."),
            ("endswith(suffix)", "Check a suffix quickly."),
            ("find(substring)", "Return the first index or -1."),
            ("isdigit()", "Validate simple numeric text before casting."),
        ],
    },
    {
        "title": "Loops, Branching, And Comprehensions",
        "concept": "Write concise transformations without losing clarity when conditions or filters appear.",
        "keywords": "for, while, if, elif, else, break, continue, list comprehension, dict comprehension",
        "syntax": """for value in values:
    if value < 0:
        continue
    if value == target:
        break

filtered = [value for value in values if value % 2 == 0]
squares = {value: value * value for value in values}

left = 0
while left < len(values):
    left += 1""",
        "tip": "Comprehensions are great for one clean transformation. If the logic becomes branch-heavy, switch back to an explicit loop.",
    },
    {
        "title": "Functions, Arguments, And Reusable Helpers",
        "concept": "Structure code into small helpers, return values clearly, and avoid hidden side effects.",
        "keywords": "def, return, args, kwargs, default arguments, docstring, helper function",
        "syntax": """def normalize_name(name, fallback="unknown"):
    cleaned = name.strip()
    return cleaned or fallback


def build_record(user_id, **extra_fields):
    return {"user_id": user_id, **extra_fields}


def outer(values):
    def helper(value):
        return value * 2

    return [helper(value) for value in values]""",
        "tip": "In interview code, prefer pure helpers that accept input and return output cleanly. That makes debugging and testing much easier.",
    },
    {
        "title": "Strings, Parsing, And Regular Expressions",
        "concept": "Clean text, split payloads, and extract structured values from unstructured strings.",
        "keywords": "split, join, strip, lower, upper, replace, startswith, endswith, re.search, re.findall, re.sub",
        "syntax": """import re

parts = line.split("|", 3)
normalized = text.strip().lower()
joined = ",".join(values)

match = re.search(r"order=(\\d+)", payload)
all_ids = re.findall(r"\\d+", payload)
cleaned = re.sub(r"\\s+", " ", text).strip()""",
        "tip": "Use plain split or replace first. Reach for regex only when the structure is truly irregular.",
        "operations": [
            ("line.split('|', 3)", "Split only the first separators and keep the rest untouched."),
            ("re.search(pattern, text)", "Find the first match object."),
            ("re.findall(pattern, text)", "Return every non-overlapping match."),
            ("re.sub(pattern, repl, text)", "Rewrite matched text."),
            ("match.group(1)", "Extract a captured subgroup from the match."),
        ],
    },
    {
        "title": "Hashing Helpers And Collections Module",
        "concept": "Use standard library helpers for counters, grouped values, queue-like structures, and combinations.",
        "keywords": "Counter, defaultdict, deque, namedtuple, combinations, heapq",
        "syntax": """from collections import Counter, defaultdict, deque
from itertools import combinations
import heapq

counts = Counter(events)
grouped = defaultdict(list)
grouped[user_id].append(record)

queue = deque([1, 2, 3])
queue.appendleft(0)
queue.pop()

smallest = heapq.nsmallest(3, values)
pairs = list(combinations(values, 2))""",
        "tip": "For data engineering and interview problems, Counter and defaultdict solve a surprising number of grouping and counting tasks quickly.",
    },
    {
        "title": "Sorting, Searching, And Complexity Thinking",
        "concept": "Know the common sort patterns and the time-complexity trade-offs behind them.",
        "keywords": "sorted, sort, key, reverse, lambda, bisect_left, O(n), O(log n), O(n log n)",
        "syntax": """from bisect import bisect_left

ordered = sorted(records, key=lambda row: (row["region"], -row["score"]))
values.sort(reverse=True)

position = bisect_left(sorted_values, target)

# Common interview targets
# single pass + hashmap -> O(n)
# sort first -> O(n log n)
# binary search -> O(log n) after sorting""",
        "tip": "If the question needs order plus efficient lookup, decide early whether a hashmap or sorting-first approach gives the cleaner complexity.",
    },
    {
        "title": "Files, CSV, JSON, And Path Handling",
        "concept": "Read and write local files safely using the standard library.",
        "keywords": "open, with, csv.DictReader, json.load, json.dump, pathlib.Path, read_text, write_text",
        "syntax": """import csv
import json
from pathlib import Path

with open("input.csv", "r", newline="") as file_obj:
    reader = csv.DictReader(file_obj)
    rows = list(reader)

with open("output.csv", "w", newline="") as file_obj:
    writer = csv.DictWriter(file_obj, fieldnames=["id", "amount"])
    writer.writeheader()
    writer.writerows(rows)

with open("input.json", "r") as file_obj:
    payload = json.load(file_obj)

json_text = json.dumps(payload, indent=2, sort_keys=True)
Path("output.txt").write_text("done")
json.dump(payload, open("output.json", "w"), indent=2)

path = Path("data")
path.exists()
path.glob("*.csv")
path.read_text()
path.write_text("done")""",
        "tip": "Always use context managers for file I/O in coding rounds. It keeps resource handling correct and the code easier to explain.",
        "operations": [
            ("open(path, mode)", "Open a local file for reading or writing."),
            ("csv.reader(file_obj)", "Read raw CSV rows as lists."),
            ("csv.DictReader(file_obj)", "Read CSV rows as dictionaries keyed by headers."),
            ("csv.writer(file_obj)", "Write list-based CSV rows."),
            ("csv.DictWriter(file_obj, fieldnames=...)", "Write dictionary-based CSV rows."),
            ("json.load(file_obj)", "Parse JSON from an open file handle."),
            ("json.loads(text)", "Parse JSON from a string."),
            ("json.dump(obj, file_obj)", "Write JSON to a file handle."),
            ("json.dumps(obj)", "Serialize JSON to a string."),
            ("Path.exists()", "Check whether a path exists."),
            ("Path.glob(pattern)", "Iterate over matching files."),
            ("Path.read_text() / write_text()", "Read or write whole text files quickly."),
        ],
    },
    {
        "title": "Datetime, Math, And Utility Modules",
        "concept": "Handle timestamps, intervals, rounding, and lightweight statistics with the standard library.",
        "keywords": "datetime, timedelta, strptime, fromisoformat, round, math.ceil, math.floor, statistics",
        "syntax": """from datetime import datetime, timedelta
import math

ts = datetime.fromisoformat("2024-01-01T10:00:00+00:00")
next_run = ts + timedelta(minutes=5)
lag_minutes = int((datetime.now(ts.tzinfo) - ts).total_seconds() // 60)

math.ceil(throughput / capacity)
round(value, 2)""",
        "tip": "For data engineering questions, timestamp parsing and safe integer rounding come up constantly in sizing, freshness, and retention problems.",
    },
    {
        "title": "Requests, APIs, And Retry Patterns",
        "concept": "Make HTTP calls, parse JSON responses, and keep retry logic idempotent.",
        "keywords": "requests.get, requests.post, timeout, raise_for_status, json, backoff, retry",
        "syntax": """import requests
import time

session = requests.Session()
response = session.get(url, params={"region": "apac"}, timeout=30)
response.raise_for_status()
payload = response.json()
headers = response.headers
raw_body = response.text

for attempt in range(3):
    try:
        response = session.post(url, json=body, headers={"X-Idempotency-Key": "job-1"}, timeout=30)
        response.raise_for_status()
        break
    except requests.RequestException:
        time.sleep(2 ** attempt)""",
        "tip": "In production-style answers, mention timeout, retry, idempotency key or checkpoint, and how failures should be surfaced.",
        "operations": [
            ("requests.Session()", "Reuse connections across many calls."),
            ("session.get(..., params=..., headers=..., timeout=...)", "Common read request pattern."),
            ("session.post(..., json=...)", "Send JSON request bodies."),
            ("session.put(...) / session.delete(...)", "Handle update and delete endpoints."),
            ("response.status_code", "Check the raw HTTP status."),
            ("response.raise_for_status()", "Fail fast on non-2xx responses."),
            ("response.json()", "Parse JSON payloads."),
            ("response.text", "Read the raw response body."),
            ("requests.RequestException", "Catch request, timeout, and connection failures."),
        ],
    },
    {
        "title": "Pandas, NumPy, And Tabular Transformations",
        "concept": "Use vectorized operations for grouped analytics, deduplication, and missing-value cleanup.",
        "keywords": "DataFrame, assign, groupby, agg, merge, sort_values, drop_duplicates, fillna, to_datetime, numpy array",
        "syntax": """import pandas as pd
import numpy as np

df["event_ts"] = pd.to_datetime(df["event_ts"])
result = (
    df.sort_values(["user_id", "event_ts"])
      .drop_duplicates(["user_id"], keep="last")
      .groupby("region", as_index=False)
      .agg(total_amount=("amount", "sum"))
)

vector = np.array(values, dtype=float)
normalized = (vector - vector.mean()) / vector.std()""",
        "tip": "In pandas questions, avoid mutating the original DataFrame unless the prompt explicitly wants in-place changes.",
    },
]


SYNTAX_EXPLANATIONS = {
    "sql": {
        "SELECT": "Chooses the columns or expressions that will appear in the final result.",
        "FROM": "Chooses the source table or derived result set where rows come from.",
        "WHERE": "Filters individual rows before grouping or aggregation happens.",
        "GROUP BY": "Collects rows into groups so aggregate functions can summarize each group.",
        "HAVING": "Filters grouped results after aggregate values have been calculated.",
        "ORDER BY": "Sorts the final result into a predictable order.",
        "LIMIT": "Returns only the requested number of rows after sorting/filtering.",
        "JOIN": "Combines rows from two tables when the ON condition matches.",
        "LEFT JOIN": "Keeps every row from the left table and fills missing right-side matches with NULL.",
        "CASE": "Creates branch logic inside a query, similar to if/elif/else.",
        "WITH": "Names a temporary query block so the main query is easier to read.",
        "OVER": "Runs a window calculation while keeping the original row detail.",
        "PARTITION BY": "Splits window calculations into independent groups.",
        "ROWS BETWEEN": "Defines the row range used by cumulative or rolling window calculations.",
        "CAST": "Converts a value from one data type to another before comparison or formatting.",
        "UNION": "Stacks compatible result sets and removes duplicates.",
        "MERGE": "Applies insert/update logic into a target table from a source table.",
        "EXPLAIN": "Shows how the database plans to execute the query.",
    },
    "pyspark": {
        "SparkSession": "The application entry point used to read data, create DataFrames, and submit jobs.",
        "spark.read": "Builds a lazy DataFrame reader for files, tables, or streams.",
        "select": "Chooses columns or expressions for the next DataFrame.",
        "filter": "Keeps rows that match a boolean Spark Column expression.",
        "withColumn": "Adds or replaces one column using a Spark expression.",
        "groupBy": "Defines grouped records before aggregation.",
        "agg": "Calculates grouped summaries such as sum, avg, or count.",
        "join": "Combines two DataFrames using a join condition and join type.",
        "when": "Creates conditional column logic inside the Spark execution plan.",
        "Window": "Defines partition, order, and frame rules for row-wise analytics.",
        "explode": "Turns array/map elements into additional rows.",
        "write": "Persists a DataFrame to files or tables.",
        "cache": "Keeps a reused DataFrame in memory after an action materializes it.",
        "repartition": "Reshuffles data into a new number of partitions.",
        "explain": "Prints the logical and physical execution plan.",
    },
    "python": {
        "def": "Defines a reusable function boundary with named inputs.",
        "return": "Sends the final value back to the caller.",
        "if": "Runs code only when a condition is true.",
        "for": "Iterates through each item in a sequence or iterable.",
        "while": "Repeats while a condition remains true.",
        "list": "Stores ordered mutable values.",
        "tuple": "Stores ordered fixed-shape values.",
        "set": "Stores unique values and gives fast membership checks.",
        "dict": "Stores key-value pairs for lookup, grouping, and counting.",
        "append": "Adds one item to the end of a list.",
        "get": "Reads from a dictionary with a fallback when the key is missing.",
        "split": "Breaks text into tokens.",
        "join": "Combines strings with a separator.",
        "with open": "Opens a file and closes it automatically after the block.",
        "json.load": "Parses JSON from a file object.",
        "requests": "Calls HTTP APIs from Python code.",
        "groupby": "Groups tabular rows in pandas before aggregation.",
        "sorted": "Returns a new ordered list without changing the original iterable.",
    },
}


def _syntax_lines(syntax):
    return [line.strip() for line in syntax.splitlines() if line.strip()]


def _explain_syntax_line(line, language):
    explanations = SYNTAX_EXPLANATIONS[language]
    upper_line = line.upper()

    for keyword, explanation in explanations.items():
        if keyword.upper() in upper_line or keyword in line:
            return explanation

    if language == "sql":
        return "This line supplies a table, expression, condition, alias, or boundary used by the query block."
    if language == "pyspark":
        return "This line adds another lazy DataFrame transformation to the Spark execution plan."
    return "This line defines data, control flow, a function call, or a transformation step in the Python program."


def _table(rows):
    return rows


def _sql_example(section):
    title = section["title"]
    examples = {
        "Core Query Skeleton": {
            "inputs": {
                "orders before query": _table([
                    {"order_id": 1, "customer": "Asha", "region": "South", "amount": 120, "status": "paid"},
                    {"order_id": 2, "customer": "Asha", "region": "South", "amount": 80, "status": "cancelled"},
                    {"order_id": 3, "customer": "Ben", "region": "West", "amount": 240, "status": "paid"},
                    {"order_id": 4, "customer": "Cara", "region": "South", "amount": 200, "status": "paid"},
                ])
            },
            "code": """SELECT region, SUM(amount) AS paid_amount
FROM orders
WHERE status = 'paid'
GROUP BY region
HAVING SUM(amount) >= 200
ORDER BY paid_amount DESC
LIMIT 2;""",
            "output": _table([
                {"region": "South", "paid_amount": 320},
                {"region": "West", "paid_amount": 240},
            ]),
            "change": "Rows are filtered first, then grouped by region, then only groups with total >= 200 remain.",
        },
        "Join Syntax": {
            "inputs": {
                "orders": _table([
                    {"order_id": 1, "customer_id": 10, "amount": 120},
                    {"order_id": 2, "customer_id": 20, "amount": 80},
                    {"order_id": 3, "customer_id": 99, "amount": 50},
                ]),
                "customers": _table([
                    {"customer_id": 10, "customer_name": "Asha"},
                    {"customer_id": 20, "customer_name": "Ben"},
                ]),
            },
            "code": """SELECT o.order_id, c.customer_name, o.amount
FROM orders AS o
LEFT JOIN customers AS c
  ON o.customer_id = c.customer_id;""",
            "output": _table([
                {"order_id": 1, "customer_name": "Asha", "amount": 120},
                {"order_id": 2, "customer_name": "Ben", "amount": 80},
                {"order_id": 3, "customer_name": None, "amount": 50},
            ]),
            "change": "The customer name is attached when keys match. The unmatched order stays because LEFT JOIN preserves left-side rows.",
        },
        "Aggregation And HAVING": {
            "inputs": {
                "sales before aggregation": _table([
                    {"region": "South", "amount": 120},
                    {"region": "South", "amount": 80},
                    {"region": "West", "amount": 240},
                    {"region": "East", "amount": 40},
                ])
            },
            "code": """SELECT region, COUNT(*) AS orders, SUM(amount) AS revenue
FROM sales
GROUP BY region
HAVING SUM(amount) >= 100;""",
            "output": _table([
                {"region": "South", "orders": 2, "revenue": 200},
                {"region": "West", "orders": 1, "revenue": 240},
            ]),
            "change": "Many order rows collapse into one row per region. HAVING removes the East group after totals are calculated.",
        },
        "Conditional Logic And NULL Handling": {
            "inputs": {
                "payments before CASE/COALESCE": _table([
                    {"payment_id": 1, "amount": 120, "coupon": None},
                    {"payment_id": 2, "amount": 40, "coupon": "NEW10"},
                    {"payment_id": 3, "amount": 0, "coupon": None},
                ])
            },
            "code": """SELECT
    payment_id,
    COALESCE(coupon, 'NO_COUPON') AS coupon_label,
    CASE
        WHEN amount >= 100 THEN 'high'
        WHEN amount > 0 THEN 'normal'
        ELSE 'free'
    END AS amount_bucket
FROM payments;""",
            "output": _table([
                {"payment_id": 1, "coupon_label": "NO_COUPON", "amount_bucket": "high"},
                {"payment_id": 2, "coupon_label": "NEW10", "amount_bucket": "normal"},
                {"payment_id": 3, "coupon_label": "NO_COUPON", "amount_bucket": "free"},
            ]),
            "change": "NULL coupon values become readable labels, and every amount is converted into a business category.",
        },
        "Subqueries, CTEs, EXISTS": {
            "inputs": {
                "orders": _table([
                    {"order_id": 1, "customer_id": 10, "amount": 120},
                    {"order_id": 2, "customer_id": 10, "amount": 80},
                    {"order_id": 3, "customer_id": 20, "amount": 40},
                ])
            },
            "code": """WITH customer_totals AS (
    SELECT customer_id, SUM(amount) AS total_amount
    FROM orders
    GROUP BY customer_id
)
SELECT customer_id, total_amount
FROM customer_totals
WHERE total_amount >= 150;""",
            "output": _table([
                {"customer_id": 10, "total_amount": 200},
            ]),
            "change": "The CTE creates an intermediate customer-level table, then the outer query filters that simpler result.",
        },
        "Window Functions": {
            "inputs": {
                "orders before window": _table([
                    {"customer": "Asha", "order_date": "2024-01-01", "amount": 120},
                    {"customer": "Asha", "order_date": "2024-01-03", "amount": 80},
                    {"customer": "Ben", "order_date": "2024-01-02", "amount": 240},
                    {"customer": "Ben", "order_date": "2024-01-05", "amount": 60},
                ])
            },
            "code": """SELECT
    customer,
    order_date,
    amount,
    SUM(amount) OVER (
        PARTITION BY customer
        ORDER BY order_date
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    ) AS running_amount
FROM orders;""",
            "output": _table([
                {"customer": "Asha", "order_date": "2024-01-01", "amount": 120, "running_amount": 120},
                {"customer": "Asha", "order_date": "2024-01-03", "amount": 80, "running_amount": 200},
                {"customer": "Ben", "order_date": "2024-01-02", "amount": 240, "running_amount": 240},
                {"customer": "Ben", "order_date": "2024-01-05", "amount": 60, "running_amount": 300},
            ]),
            "change": "No rows are collapsed. A running total is added within each customer partition.",
        },
        "String, Date, And Type Conversion": {
            "inputs": {
                "raw_events": _table([
                    {"event_id": 1, "raw_name": "  ASHA ", "event_ts": "2024-01-15 10:30:00"},
                    {"event_id": 2, "raw_name": " ben", "event_ts": "2024-02-02 09:00:00"},
                ])
            },
            "code": """SELECT
    event_id,
    LOWER(TRIM(raw_name)) AS clean_name,
    DATE_FORMAT(CAST(event_ts AS DATETIME), '%Y-%m') AS event_month
FROM raw_events;""",
            "output": _table([
                {"event_id": 1, "clean_name": "asha", "event_month": "2024-01"},
                {"event_id": 2, "clean_name": "ben", "event_month": "2024-02"},
            ]),
            "change": "Messy strings are normalized and timestamp text is converted into a month-level value.",
        },
        "Set Operations And Deduplication": {
            "inputs": {
                "web_users": _table([{"user_id": 1}, {"user_id": 2}, {"user_id": 2}]),
                "app_users": _table([{"user_id": 2}, {"user_id": 3}]),
            },
            "code": """SELECT user_id FROM web_users
UNION
SELECT user_id FROM app_users;""",
            "output": _table([
                {"user_id": 1},
                {"user_id": 2},
                {"user_id": 3},
            ]),
            "change": "UNION stacks both inputs and removes duplicate user_id values.",
        },
        "Ranking, Top-N, Pagination": {
            "inputs": {
                "sales": _table([
                    {"region": "South", "rep": "Asha", "revenue": 300},
                    {"region": "South", "rep": "Ben", "revenue": 250},
                    {"region": "West", "rep": "Cara", "revenue": 500},
                    {"region": "West", "rep": "Dev", "revenue": 200},
                ])
            },
            "code": """SELECT region, rep, revenue
FROM (
    SELECT *,
           ROW_NUMBER() OVER (
               PARTITION BY region
               ORDER BY revenue DESC
           ) AS rn
    FROM sales
) ranked
WHERE rn = 1;""",
            "output": _table([
                {"region": "South", "rep": "Asha", "revenue": 300},
                {"region": "West", "rep": "Cara", "revenue": 500},
            ]),
            "change": "Rows are ranked inside each region, then only the top row from each region is kept.",
        },
        "Recursive CTEs, Pivot, Rollup, JSON": {
            "inputs": {
                "monthly_sales": _table([
                    {"region": "South", "month": "Jan", "amount": 100},
                    {"region": "South", "month": "Feb", "amount": 150},
                    {"region": "West", "month": "Jan", "amount": 200},
                ])
            },
            "code": """SELECT
    region,
    SUM(CASE WHEN month = 'Jan' THEN amount ELSE 0 END) AS jan_amount,
    SUM(CASE WHEN month = 'Feb' THEN amount ELSE 0 END) AS feb_amount
FROM monthly_sales
GROUP BY region;""",
            "output": _table([
                {"region": "South", "jan_amount": 100, "feb_amount": 150},
                {"region": "West", "jan_amount": 200, "feb_amount": 0},
            ]),
            "change": "Rows for months are rotated into separate month columns using conditional aggregation.",
        },
        "Data Engineering Patterns": {
            "inputs": {
                "target_customer_dim": _table([
                    {"customer_id": 10, "name": "Asha", "city": "Chennai", "current_flag": 1},
                    {"customer_id": 20, "name": "Ben", "city": "Pune", "current_flag": 1},
                ]),
                "source_updates": _table([
                    {"customer_id": 10, "name": "Asha", "city": "Bengaluru"},
                    {"customer_id": 30, "name": "Cara", "city": "Mumbai"},
                ]),
            },
            "code": """MERGE INTO target_customer_dim AS t
USING source_updates AS s
  ON t.customer_id = s.customer_id
WHEN MATCHED THEN
  UPDATE SET city = s.city
WHEN NOT MATCHED THEN
  INSERT (customer_id, name, city, current_flag)
  VALUES (s.customer_id, s.name, s.city, 1);""",
            "output": _table([
                {"customer_id": 10, "name": "Asha", "city": "Bengaluru", "current_flag": 1},
                {"customer_id": 20, "name": "Ben", "city": "Pune", "current_flag": 1},
                {"customer_id": 30, "name": "Cara", "city": "Mumbai", "current_flag": 1},
            ]),
            "change": "Existing business keys are updated and new business keys are inserted in one idempotent write pattern.",
        },
        "Analytics Metrics And Product Patterns": {
            "inputs": {
                "events": _table([
                    {"user_id": 1, "event": "signup", "event_date": "2024-01-01"},
                    {"user_id": 1, "event": "purchase", "event_date": "2024-01-03"},
                    {"user_id": 2, "event": "signup", "event_date": "2024-01-01"},
                    {"user_id": 3, "event": "purchase", "event_date": "2024-01-03"},
                ])
            },
            "code": """SELECT
    COUNT(DISTINCT CASE WHEN event = 'signup' THEN user_id END) AS signups,
    COUNT(DISTINCT CASE WHEN event = 'purchase' THEN user_id END) AS purchasers
FROM events;""",
            "output": _table([
                {"signups": 2, "purchasers": 2},
            ]),
            "change": "Conditional DISTINCT counts turn raw event rows into product metrics.",
        },
        "Plan, Debug, And Sanity Checks": {
            "inputs": {
                "orders": _table([
                    {"order_id": 1, "customer_id": 10, "amount": 120},
                    {"order_id": 2, "customer_id": 10, "amount": 80},
                    {"order_id": 2, "customer_id": 10, "amount": 80},
                ])
            },
            "code": """SELECT
    COUNT(*) AS row_count,
    COUNT(DISTINCT order_id) AS distinct_orders,
    COUNT(*) - COUNT(DISTINCT order_id) AS duplicate_rows
FROM orders;""",
            "output": _table([
                {"row_count": 3, "distinct_orders": 2, "duplicate_rows": 1},
            ]),
            "change": "A sanity query exposes duplicate grain before trusting downstream joins or aggregations.",
        },
    }
    return examples.get(title, examples["Core Query Skeleton"])


def _python_example(section):
    title = section["title"]
    examples = {
        "Core Script Skeleton And Input Handling": {
            "inputs": {"stdin / function input": _table([{"raw": "10 20 30", "meaning": "three numbers as text"}])},
            "code": """def solve(values):
    return sum(values)

raw = "10 20 30"
values = list(map(int, raw.split()))
answer = solve(values)""",
            "output": _table([{"values": "[10, 20, 30]", "answer": 60}]),
            "change": "Raw text is split, converted into integers, passed into a function, and returned as one result.",
        },
        "Lists, Tuples, Sets, And Dictionaries": {
            "inputs": {"events": _table([{"events": "['click', 'view', 'click']", "user_pair": "('u1', 120)"}])},
            "code": """events = ['click', 'view', 'click']
unique_events = set(events)
counts = {}
for event in events:
    counts[event] = counts.get(event, 0) + 1""",
            "output": _table([{"unique_events": "{'click', 'view'}", "counts": "{'click': 2, 'view': 1}"}]),
            "change": "A list keeps order, a set removes duplicates, and a dict stores counts by key.",
        },
        "List Operations And Mutability": {
            "inputs": {"nums before": _table([{"nums": "[10, 20, 30]"}])},
            "code": """nums = [10, 20, 30]
nums.append(40)
removed = nums.pop(1)
evens = [x for x in nums if x % 2 == 0]""",
            "output": _table([{"nums_after": "[10, 30, 40]", "removed": 20, "evens": "[10, 30, 40]"}]),
            "change": "append and pop mutate the original list; the comprehension creates a new filtered list.",
        },
        "Tuple Operations And Immutability": {
            "inputs": {"records": _table([{"record": "('us', 'prod', 120)"}])},
            "code": """record = ('us', 'prod', 120)
region, env, amount = record
lookup_key = (region, env)
metrics = {lookup_key: amount}""",
            "output": _table([{"region": "us", "env": "prod", "metrics": "{('us', 'prod'): 120}"}]),
            "change": "A fixed tuple is unpacked into variables and reused as a safe dictionary key.",
        },
        "Set Operations And Membership": {
            "inputs": {"ids": _table([{"left": "{1, 2, 3}", "right": "{3, 4}"}])},
            "code": """left = {1, 2, 3}
right = {3, 4}
union_ids = left | right
common_ids = left & right
new_only = right - left""",
            "output": _table([{"union_ids": "{1, 2, 3, 4}", "common_ids": "{3}", "new_only": "{4}"}]),
            "change": "Set operators compare groups of values without manual loops.",
        },
        "Dictionary Operations And Update Patterns": {
            "inputs": {"events": _table([{"events": "['click', 'view', 'click']"}])},
            "code": """counts = {}
for event in ['click', 'view', 'click']:
    counts[event] = counts.get(event, 0) + 1

record = {'id': 1, 'status': 'new'}
record.update({'status': 'done'})""",
            "output": _table([{"counts": "{'click': 2, 'view': 1}", "record": "{'id': 1, 'status': 'done'}"}]),
            "change": "get prevents missing-key errors during counting; update changes only the provided fields.",
        },
        "String Operations And Type Conversion": {
            "inputs": {"raw text": _table([{"text": "  Order-101 | 19.95  "}])},
            "code": """text = "  Order-101 | 19.95  "
clean = text.strip()
order_id, price_text = [part.strip() for part in clean.split("|")]
price = float(price_text)""",
            "output": _table([{"order_id": "Order-101", "price_text": "19.95", "price": 19.95}]),
            "change": "Whitespace is removed, text is split into fields, and numeric text becomes a float.",
        },
        "Loops, Branching, And Comprehensions": {
            "inputs": {"numbers": _table([{"values": "[-2, 3, 4, 7]"}])},
            "code": """values = [-2, 3, 4, 7]
labels = []
for value in values:
    if value < 0:
        labels.append("negative")
    elif value % 2 == 0:
        labels.append("even")
    else:
        labels.append("odd")""",
            "output": _table([{"labels": "['negative', 'odd', 'even', 'odd']"}]),
            "change": "Each input value travels through branch rules and produces one label.",
        },
        "Functions, Arguments, And Reusable Helpers": {
            "inputs": {"names": _table([{"name": "  Asha  "}, {"name": ""}])},
            "code": """def normalize_name(name, fallback="unknown"):
    cleaned = name.strip()
    return cleaned or fallback

result = [normalize_name("  Asha  "), normalize_name("")]""",
            "output": _table([{"result": "['Asha', 'unknown']"}]),
            "change": "The helper centralizes cleanup logic and returns predictable output for normal and empty input.",
        },
        "Strings, Parsing, And Regular Expressions": {
            "inputs": {"payloads": _table([{"payload": "order=101 amount=25"}, {"payload": "order=102 amount=40"}])},
            "code": """import re
payload = "order=101 amount=25"
order_id = re.search(r"order=(\\d+)", payload).group(1)
numbers = re.findall(r"\\d+", payload)""",
            "output": _table([{"order_id": "101", "numbers": "['101', '25']"}]),
            "change": "Regex extracts structured values from unstructured text.",
        },
        "Hashing Helpers And Collections Module": {
            "inputs": {"events": _table([{"events": "['click', 'view', 'click', 'buy']"}])},
            "code": """from collections import Counter, defaultdict
events = ['click', 'view', 'click', 'buy']
counts = Counter(events)
grouped = defaultdict(list)
for event in events:
    grouped[event[0]].append(event)""",
            "output": _table([{"counts": "Counter({'click': 2, 'view': 1, 'buy': 1})", "grouped": "{'c': ['click', 'click'], 'v': ['view'], 'b': ['buy']}"}]),
            "change": "Counter handles frequency counting and defaultdict handles grouped lists with less boilerplate.",
        },
        "Sorting, Searching, And Complexity Thinking": {
            "inputs": {"records": _table([
                {"user": "Asha", "score": 80},
                {"user": "Ben", "score": 95},
                {"user": "Cara", "score": 90},
            ])},
            "code": """records = [{'user': 'Asha', 'score': 80}, {'user': 'Ben', 'score': 95}, {'user': 'Cara', 'score': 90}]
ordered = sorted(records, key=lambda row: row['score'], reverse=True)
top_user = ordered[0]['user']""",
            "output": _table([
                {"rank": 1, "user": "Ben", "score": 95},
                {"rank": 2, "user": "Cara", "score": 90},
                {"rank": 3, "user": "Asha", "score": 80},
            ]),
            "change": "Sorting reorders the records by score so the top item becomes easy to read.",
        },
        "Files, CSV, JSON, And Path Handling": {
            "inputs": {"input.json": _table([{"file_text": '{"orders": [{"id": 1, "amount": 20}, {"id": 2, "amount": 30}]}' }])},
            "code": """import json
payload = {"orders": [{"id": 1, "amount": 20}, {"id": 2, "amount": 30}]}
total = sum(row["amount"] for row in payload["orders"])
output_text = json.dumps({"total": total})""",
            "output": _table([{"parsed_orders": 2, "total": 50, "output_text": '{"total": 50}'}]),
            "change": "JSON text becomes Python dictionaries/lists, then Python result data can be serialized back to JSON.",
        },
        "Datetime, Math, And Utility Modules": {
            "inputs": {"timestamps": _table([{"start": "2024-01-01 10:00", "end": "2024-01-01 11:45"}])},
            "code": """from datetime import datetime
import math
start = datetime.fromisoformat("2024-01-01 10:00")
end = datetime.fromisoformat("2024-01-01 11:45")
minutes = int((end - start).total_seconds() / 60)
batches = math.ceil(minutes / 60)""",
            "output": _table([{"minutes": 105, "batches": 2}]),
            "change": "Timestamp strings become datetime objects, duration becomes minutes, and ceil rounds capacity upward.",
        },
        "Requests, APIs, And Retry Patterns": {
            "inputs": {"api response": _table([{"status_code": 200, "body": '{"id": 1, "status": "ok"}'}])},
            "code": """response_json = {"id": 1, "status": "ok"}
record = {
    "id": response_json["id"],
    "is_success": response_json["status"] == "ok",
}""",
            "output": _table([{"id": 1, "is_success": True}]),
            "change": "An external JSON response is validated and reshaped into the fields the pipeline needs.",
        },
        "Pandas, NumPy, And Tabular Transformations": {
            "inputs": {"df before": _table([
                {"user_id": 1, "event_ts": "2024-01-01", "amount": 20},
                {"user_id": 1, "event_ts": "2024-01-03", "amount": 30},
                {"user_id": 2, "event_ts": "2024-01-02", "amount": 40},
            ])},
            "code": """result = (
    df.sort_values(["user_id", "event_ts"])
      .drop_duplicates(["user_id"], keep="last")
      .groupby("user_id", as_index=False)
      .agg(latest_amount=("amount", "sum"))
)""",
            "output": _table([
                {"user_id": 1, "latest_amount": 30},
                {"user_id": 2, "latest_amount": 40},
            ]),
            "change": "The table is sorted, reduced to latest row per user, then summarized in a vectorized way.",
        },
    }
    return examples.get(title, examples["Core Script Skeleton And Input Handling"])


def _pyspark_example(section):
    title = section["title"]
    base_input = _table([
        {"user_id": 1, "region": "South", "amount": 120, "event_date": "2024-01-01"},
        {"user_id": 1, "region": "South", "amount": 80, "event_date": "2024-01-03"},
        {"user_id": 2, "region": "West", "amount": 240, "event_date": "2024-01-02"},
    ])
    if "Join" in title:
        return {
            "inputs": {
                "orders_df": base_input,
                "users_df": _table([{"user_id": 1, "name": "Asha"}, {"user_id": 2, "name": "Ben"}]),
            },
            "code": """result = orders_df.join(users_df, "user_id", "left")""",
            "output": _table([
                {"user_id": 1, "region": "South", "amount": 120, "name": "Asha"},
                {"user_id": 1, "region": "South", "amount": 80, "name": "Asha"},
                {"user_id": 2, "region": "West", "amount": 240, "name": "Ben"},
            ]),
            "change": "Spark creates a joined DataFrame plan; rows execute only when an action like show/count/write runs.",
        }
    if "Aggregation" in title:
        code = """result = orders_df.groupBy("region").agg(
    sum("amount").alias("revenue"),
    count("*").alias("orders")
)"""
        output = _table([{"region": "South", "revenue": 200, "orders": 2}, {"region": "West", "revenue": 240, "orders": 1}])
    elif "Window" in title:
        code = """window_spec = Window.partitionBy("user_id").orderBy("event_date")
result = orders_df.withColumn(
    "running_amount",
    sum("amount").over(window_spec)
)"""
        output = _table([
            {"user_id": 1, "event_date": "2024-01-01", "amount": 120, "running_amount": 120},
            {"user_id": 1, "event_date": "2024-01-03", "amount": 80, "running_amount": 200},
            {"user_id": 2, "event_date": "2024-01-02", "amount": 240, "running_amount": 240},
        ])
    elif "Conditional" in title:
        code = """result = orders_df.withColumn(
    "amount_bucket",
    when(col("amount") >= 100, "high").otherwise("normal")
)"""
        output = _table([
            {"user_id": 1, "amount": 120, "amount_bucket": "high"},
            {"user_id": 1, "amount": 80, "amount_bucket": "normal"},
            {"user_id": 2, "amount": 240, "amount_bucket": "high"},
        ])
    elif "Date" in title:
        code = """result = orders_df.withColumn("event_dt", to_date(col("event_date"))) \\
    .withColumn("event_month", date_format(col("event_dt"), "yyyy-MM"))"""
        output = _table([
            {"user_id": 1, "event_dt": "2024-01-01", "event_month": "2024-01"},
            {"user_id": 1, "event_dt": "2024-01-03", "event_month": "2024-01"},
            {"user_id": 2, "event_dt": "2024-01-02", "event_month": "2024-01"},
        ])
    elif "Complex Types" in title:
        code = """result = users_df.withColumn("tag", explode(col("tags")))"""
        return {
            "inputs": {"users_df": _table([{"user_id": 1, "tags": "['sql', 'spark']"}, {"user_id": 2, "tags": "['python']"}])},
            "code": code,
            "output": _table([{"user_id": 1, "tag": "sql"}, {"user_id": 1, "tag": "spark"}, {"user_id": 2, "tag": "python"}]),
            "change": "explode converts each array element into its own row.",
        }
    elif "Union" in title:
        code = """result = df_a.unionByName(df_b).dropDuplicates(["user_id"])"""
        return {
            "inputs": {"df_a": _table([{"user_id": 1}, {"user_id": 2}]), "df_b": _table([{"user_id": 2}, {"user_id": 3}])},
            "code": code,
            "output": _table([{"user_id": 1}, {"user_id": 2}, {"user_id": 3}]),
            "change": "DataFrames are stacked by column name and duplicates are removed.",
        }
    elif "Actions" in title or "Explain" in title or "RDD" in title or "Write" in title or "Read" in title or "Spark Session" in title:
        code = """orders_df = spark.createDataFrame(rows)
orders_df.printSchema()
orders_df.show()
orders_df.explain("formatted")"""
        output = _table([{"visible_effect": "schema printed, rows displayed, physical plan explained"}])
    else:
        code = """result = (
    orders_df
    .filter(col("amount") >= 100)
    .withColumn("double_amount", col("amount") * 2)
    .select("user_id", "region", "double_amount")
)"""
        output = _table([
            {"user_id": 1, "region": "South", "double_amount": 240},
            {"user_id": 2, "region": "West", "double_amount": 480},
        ])

    return {
        "inputs": {"orders_df before": base_input},
        "code": code,
        "output": output,
        "change": "The DataFrame is not changed in place; Spark returns a new lazy DataFrame plan that produces this output when executed.",
    }


def _concept_example(section, language):
    if language == "sql":
        return _sql_example(section)
    if language == "pyspark":
        return _pyspark_example(section)
    return _python_example(section)


def _render_table_block(label, rows):
    st.markdown(f"**{label}**")
    st.dataframe(rows, use_container_width=True, hide_index=True)


def render_practical_example(section, language, code_language):
    example = _concept_example(section, language)
    st.markdown("#### Practical Execution View")
    st.caption("Read this as: input data before execution -> code/syntax -> output data after execution.")

    input_col, output_col = st.columns(2)
    with input_col:
        st.markdown("**Before execution: input data**")
        for label, rows in example["inputs"].items():
            _render_table_block(label, rows)

    with output_col:
        st.markdown("**After execution: output data**")
        _render_table_block("result", example["output"])

    st.markdown("**Code that creates the after table/data**")
    st.code(example["code"], language=code_language, wrap_lines=True)
    st.success(f"What changed: {example['change']}")

    with st.expander("Line-by-line syntax meaning"):
        for line in _syntax_lines(example["code"])[:12]:
            st.markdown(f"- `{line}`: {_explain_syntax_line(line, language)}")


def render_reference_section(section, code_language, concept_language):
    with st.container(border=True):
        st.markdown(f"### {section['title']}")
        st.markdown(f"**What it refers to**: {section['concept']}")
        st.markdown(f"**Key syntax / keywords**: `{section['keywords']}`")
        render_practical_example(section, concept_language, code_language)
        if section.get("operations"):
            st.markdown("**Common operations index**")
            for operation_name, operation_summary in section["operations"]:
                st.markdown(f"- `{operation_name}`: {operation_summary}")
        with st.expander("Reusable syntax template"):
            st.code(section["syntax"], language=code_language, wrap_lines=True)
        st.markdown(f"**How to think about it**: {section['tip']}")


def render_reference_tab(title, caption, sections, code_language, key_prefix, concept_language=None):
    st.subheader(title)
    st.caption(caption)
    concept_language = concept_language or code_language

    view_mode = st.radio(
        "Study mode",
        ["One concept at a time", "All concepts"],
        horizontal=True,
        key=f"{key_prefix}_view_mode",
    )

    section_titles = [section["title"] for section in sections]

    if view_mode == "One concept at a time":
        selected_title = st.selectbox(
            "Choose a concept",
            section_titles,
            key=f"{key_prefix}_selected_title",
        )
        selected_section = next(section for section in sections if section["title"] == selected_title)
        render_reference_section(selected_section, code_language, concept_language)
    else:
        st.caption("Showing all concepts in a full-width reading view.")
        for section in sections:
            render_reference_section(section, code_language, concept_language)


def render_concepts():
    st.title("Syntax Concepts")
    st.write(
        "This page is a generic reference, not a question-specific guide. Use it to understand what each concept "
        "means, which keywords belong to it, and the reusable syntax patterns you can apply in interviews."
    )
    st.info(
        "The SQL side is written in MySQL-style interview syntax. PySpark covers DataFrame API concepts end to end, "
        "and Python now includes interview-ready syntax for data structures, files, APIs, pandas, and complexity patterns."
    )
    st.caption(
        "The layout is now optimized for studying: use the full page width, switch between SQL, PySpark, and Python tabs, "
        "and focus on one concept at a time when you want a cleaner reading flow."
    )

    sql_tab, pyspark_tab, python_tab = st.tabs(["SQL Reference", "PySpark Reference", "Python Reference"])

    with sql_tab:
        render_reference_tab(
            title="SQL Reference",
            caption="Generic SQL syntax patterns and key terms. These are reusable templates, not dataset-specific code.",
            sections=SQL_CONCEPT_SECTIONS,
            code_language="sql",
            key_prefix="sql_reference",
        )

    with pyspark_tab:
        render_reference_tab(
            title="PySpark Reference",
            caption="Independent PySpark concepts with reusable DataFrame syntax, from session entry points to nested data and execution behavior.",
            sections=PYSPARK_CONCEPT_SECTIONS,
            code_language="python",
            key_prefix="pyspark_reference",
            concept_language="pyspark",
        )

    with python_tab:
        render_reference_tab(
            title="Python Reference",
            caption="Interview-ready Python syntax covering core coding, data structures, files, APIs, pandas, and data-engineering utility patterns.",
            sections=PYTHON_CONCEPT_SECTIONS,
            code_language="python",
            key_prefix="python_reference",
        )
