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

with open("input.json", "r") as file_obj:
    payload = json.load(file_obj)

Path("output.txt").write_text("done")
json.dump(payload, open("output.json", "w"), indent=2)""",
        "tip": "Always use context managers for file I/O in coding rounds. It keeps resource handling correct and the code easier to explain.",
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

response = requests.get(url, timeout=30)
response.raise_for_status()
payload = response.json()

for attempt in range(3):
    try:
        response = requests.post(url, json=body, timeout=30)
        response.raise_for_status()
        break
    except requests.RequestException:
        time.sleep(2 ** attempt)""",
        "tip": "In production-style answers, mention timeout, retry, idempotency key or checkpoint, and how failures should be surfaced.",
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


def render_reference_section(section, language):
    with st.container(border=True):
        st.markdown(f"### {section['title']}")
        st.markdown(f"**What it refers to**: {section['concept']}")
        st.markdown(f"**Key syntax / keywords**: `{section['keywords']}`")
        st.code(section["syntax"], language=language, wrap_lines=True)
        st.markdown(f"**How to think about it**: {section['tip']}")


def render_reference_tab(title, caption, sections, language, key_prefix):
    st.subheader(title)
    st.caption(caption)

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
        render_reference_section(selected_section, language)
    else:
        st.caption("Showing all concepts in a full-width reading view.")
        for section in sections:
            render_reference_section(section, language)


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
            language="sql",
            key_prefix="sql_reference",
        )

    with pyspark_tab:
        render_reference_tab(
            title="PySpark Reference",
            caption="Independent PySpark concepts with reusable DataFrame syntax, from session entry points to nested data and execution behavior.",
            sections=PYSPARK_CONCEPT_SECTIONS,
            language="python",
            key_prefix="pyspark_reference",
        )

    with python_tab:
        render_reference_tab(
            title="Python Reference",
            caption="Interview-ready Python syntax covering core coding, data structures, files, APIs, pandas, and data-engineering utility patterns.",
            sections=PYTHON_CONCEPT_SECTIONS,
            language="python",
            key_prefix="python_reference",
        )
