import streamlit as st


def _render_node(title: str, subtitle: str, bullets: list[str]) -> None:
    with st.container(border=True):
        st.markdown(f"### {title}")
        st.caption(subtitle)
        for bullet in bullets:
            st.markdown(f"- {bullet}")


def _render_executor(title: str, tasks: list[str], notes: list[str]) -> None:
    with st.container(border=True):
        st.markdown(f"**{title}**")
        task_cols = st.columns(len(tasks))
        for index, task in enumerate(tasks):
            task_cols[index].metric("Task Slot", task)

        mem_col1, mem_col2 = st.columns(2)
        with mem_col1:
            st.info(
                "\n".join(
                    [
                        "**Execution Memory**",
                        "",
                        "- joins",
                        "- sorts",
                        "- aggregations",
                        "- shuffle buffers",
                    ]
                )
            )
        with mem_col2:
            st.success(
                "\n".join(
                    [
                        "**Storage Memory**",
                        "",
                        "- cache / persist",
                        "- broadcast blocks",
                        "- reused partitions",
                        "- state store pages",
                    ]
                )
            )

        for note in notes:
            st.markdown(f"- {note}")


def _render_signal_card(title: str, body: list[str], tone: str = "info") -> None:
    with st.container(border=True):
        st.markdown(f"**{title}**")
        content = "\n".join(f"- {line}" for line in body)
        if tone == "warning":
            st.warning(content)
        elif tone == "success":
            st.success(content)
        elif tone == "error":
            st.error(content)
        else:
            st.info(content)


def _render_architecture_diagram() -> None:
    st.subheader("Spark Architecture Diagram")
    st.info(
        "Execution chain: user action -> SparkSession / driver planning -> cluster manager resource allocation -> "
        "stages -> tasks on executors -> shuffle / cache / result."
    )

    top_col1, top_arrow1, top_col2, top_arrow2, top_col3 = st.columns(
        [2.4, 0.3, 2.0, 0.3, 3.6],
        gap="small",
    )

    with top_col1:
        _render_node(
            "Driver",
            "SparkSession entry point and control plane",
            [
                "SparkSession receives DataFrame / SQL / streaming code.",
                "SparkContext holds the connection to the cluster.",
                "Catalyst builds the logical plan and chooses a physical plan.",
                "DAG Scheduler breaks the plan into stages and tasks.",
                "The driver coordinates execution and returns the final result.",
            ],
        )

    with top_arrow1:
        st.markdown("")
        st.markdown("")
        st.markdown("## ->")

    with top_col2:
        _render_node(
            "Cluster Manager",
            "Where resources come from",
            [
                "YARN, Kubernetes, or Standalone decides where executors run.",
                "Allocates CPU and memory for executors.",
                "Launches executors on worker nodes.",
                "Does not optimize queries; it only manages resources.",
            ],
        )

    with top_arrow2:
        st.markdown("")
        st.markdown("")
        st.markdown("## ->")

    with top_col3:
        with st.container(border=True):
            st.markdown("### Worker Nodes And Executors")
            st.caption("Where tasks actually run")
            st.markdown(
                "- Each executor is a JVM process with task slots, execution memory, storage memory, shuffle files, and cached blocks."
            )
            st.markdown(
                "- Wide transformations force data movement across executors, which creates shuffle cost and failure risk."
            )

            exec_col1, exec_col2 = st.columns(2, gap="small")
            with exec_col1:
                _render_executor(
                    "Executor 1",
                    ["Task 1", "Task 2"],
                    [
                        "Can run multiple tasks in parallel depending on cores.",
                        "Spill happens if execution memory is not enough.",
                    ],
                )
            with exec_col2:
                _render_executor(
                    "Executor 2",
                    ["Task 3", "Task 4"],
                    [
                        "Reads shuffle blocks produced by earlier stages.",
                        "Long-tail tasks here usually indicate skew or large partitions.",
                    ],
                )

    st.markdown("")
    with st.container(border=True):
        st.markdown("### Spark UI And Runtime Signals")
        ui_col1, ui_col2, ui_col3, ui_col4, ui_col5 = st.columns(5, gap="small")
        ui_col1.info("Jobs -> Stages -> Tasks")
        ui_col2.warning("Shuffle Read / Write")
        ui_col3.error("Spill / OOM / GC")
        ui_col4.info("Skew / Long Tail Tasks")
        ui_col5.success("Executor Loss / Retries")


def _render_execution_walkthrough() -> None:
    st.subheader("How The Architecture Executes")

    flow_col1, flow_col2 = st.columns([1.25, 1], gap="large")

    with flow_col1:
        st.markdown(
            """
            1. **You write transformations** on DataFrames, RDDs, or streaming inputs.
            2. **Nothing runs immediately** until an action or sink is triggered.
            3. **The driver builds a logical plan** that describes what should happen.
            4. **Catalyst optimizer rewrites the plan** using rules like predicate pushdown, column pruning, and join selection.
            5. **Spark produces a physical plan** with operators such as broadcast hash join or sort-merge join.
            6. **DAG Scheduler cuts the plan into stages** at shuffle boundaries.
            7. **Each stage becomes tasks** and those tasks are sent to executors.
            8. **Executors run tasks on partitions** and exchange data only when a shuffle is required.
            9. **Results are returned** to the driver, written to storage, or kept as streaming output.
            """
        )

    with flow_col2:
        st.success(
            """
            **Interview shortcut**

            If you need to explain Spark quickly, say:

            "SparkSession is the entry point. The driver creates the logical plan,
            Catalyst optimizes it, Spark builds a physical plan, the DAG scheduler
            splits it into stages at shuffle boundaries, and executors run tasks on
            partitions across the cluster."
            """
        )
        st.info(
            """
            **Most important boundary**

            The biggest concept in Spark architecture is the **shuffle boundary**.
            That is usually where jobs become slower, more memory-heavy, and more
            failure-prone.
            """
        )


def _render_memory_and_shuffle() -> None:
    st.subheader("Memory Model, Shuffle, And Performance")

    mem_col1, mem_col2 = st.columns(2, gap="large")

    with mem_col1:
        _render_signal_card(
            "Unified Memory Model",
            [
                "Execution memory is used by active computation such as joins, sorts, aggregations, and shuffle processing.",
                "Storage memory is used by cached data, persisted blocks, and broadcast state.",
                "Execution can evict storage if more working memory is needed.",
                "Large cache plus large shuffle is a common reason for OOM.",
            ],
            tone="info",
        )
        _render_signal_card(
            "Why OOM Happens",
            [
                "Huge partitions after a wide transformation.",
                "Data skew that sends too much data to one task.",
                "Over-caching intermediate data that is not reused.",
                "Collecting too much data back to the driver.",
                "Using the wrong join strategy for table size.",
            ],
            tone="error",
        )

    with mem_col2:
        _render_signal_card(
            "Stages And Shuffle",
            [
                "Narrow transformations usually stay in the same stage because data stays in partition order.",
                "Wide transformations like groupBy, distinct, repartition, and many joins create shuffle and a new stage.",
                "Shuffle means network I/O, disk I/O, serialization cost, and spill risk.",
                "The performance goal is to reduce unnecessary wide transformations.",
            ],
            tone="warning",
        )
        _render_signal_card(
            "How To Reduce Shuffle Pain",
            [
                "Use broadcast joins when one side is small enough.",
                "Repartition only when it helps downstream balance.",
                "Avoid repeated wide operations on the same data.",
                "Watch partition sizing so you do not create too many tiny or too few huge partitions.",
            ],
            tone="success",
        )


def _render_fault_tolerance() -> None:
    st.subheader("Fault Tolerance And Failure Handling")

    fault_col1, fault_col2 = st.columns(2, gap="large")

    with fault_col1:
        _render_signal_card(
            "RDD Lineage And Recovery",
            [
                "RDD lineage records how each partition was built from earlier transformations.",
                "If an executor or partition is lost, Spark can recompute the missing partition from lineage.",
                "This is why Spark does not need to replicate every intermediate partition by default.",
                "Checkpointing is used when lineage becomes very long or when stateful streaming needs durable recovery.",
            ],
            tone="info",
        )
        _render_signal_card(
            "Automatic Retries",
            [
                "Task failures are retried automatically.",
                "If enough tasks fail in a stage, Spark can rerun the stage.",
                "Speculative execution can rerun a slow straggler task on another executor.",
                "Executor loss is usually recoverable unless the driver or external state becomes the bottleneck.",
            ],
            tone="success",
        )

    with fault_col2:
        _render_signal_card(
            "What To Say In Failure Questions",
            [
                "If a task fails, Spark retries it.",
                "If an executor dies, Spark reschedules lost tasks on another executor.",
                "If cached data is lost, it can be recomputed unless it was only driver-side state.",
                "For streaming, checkpoint location and sink semantics decide how safely the query resumes.",
            ],
            tone="warning",
        )
        _render_signal_card(
            "Common Failure Hotspots",
            [
                "Executor OOM during large joins or aggregations.",
                "Driver OOM due to collect or large broadcast creation.",
                "Skew causing one partition to run much longer than the rest.",
                "Streaming jobs without durable checkpoints.",
                "External sink writes that are not idempotent on restart.",
            ],
            tone="error",
        )


def _render_advanced_topics() -> None:
    st.subheader("Optimizer, AQE, Streaming, And Data Sources")

    advanced_col1, advanced_col2 = st.columns(2, gap="large")

    with advanced_col1:
        _render_signal_card(
            "Catalyst Optimizer",
            [
                "Builds the logical plan and rewrites it with optimization rules.",
                "Important ideas are predicate pushdown, column pruning, constant folding, and join reordering.",
                "Catalyst is about plan optimization, not cluster resource allocation.",
                "The physical plan decides which concrete operators Spark will execute.",
            ],
            tone="info",
        )
        _render_signal_card(
            "Adaptive Query Execution",
            [
                "AQE uses runtime statistics rather than only compile-time estimates.",
                "Can coalesce shuffle partitions.",
                "Can split skewed partitions.",
                "Can switch a sort-merge join to broadcast hash join when one side becomes small enough.",
            ],
            tone="success",
        )

    with advanced_col2:
        _render_signal_card(
            "Structured Streaming",
            [
                "Treats streaming queries as incremental tables.",
                "Micro-batch is the common processing model.",
                "Checkpointing stores progress, offsets, and state metadata for restart.",
                "Watermarks control late data handling and state growth.",
            ],
            tone="warning",
        )
        _render_signal_card(
            "Data Source Layer",
            [
                "Common formats: Parquet, ORC, JSON, CSV, Delta Lake, Iceberg, Hudi.",
                "Common sources: Kafka, Kinesis, JDBC systems, S3, ADLS, GCS, HDFS.",
                "Storage format, partitioning, and file size strongly affect Spark performance.",
                "In interviews, separate source design, compute design, and cluster design clearly.",
            ],
            tone="info",
        )


def render_spark() -> None:
    st.title("Spark")
    st.caption(
        "Architecture-first Spark study page for interviews: diagram first, then execution, shuffle, memory, "
        "fault tolerance, failure handling, AQE, and streaming."
    )

    _render_architecture_diagram()
    st.divider()

    walkthrough_tab, memory_tab, fault_tab, advanced_tab = st.tabs(
        [
            "Execution Flow",
            "Memory And Shuffle",
            "Fault Tolerance",
            "Advanced Topics",
        ]
    )

    with walkthrough_tab:
        _render_execution_walkthrough()

    with memory_tab:
        _render_memory_and_shuffle()

    with fault_tab:
        _render_fault_tolerance()

    with advanced_tab:
        _render_advanced_topics()

    st.divider()
    st.subheader("How To Explain This Architecture In One Strong Answer")
    st.markdown(
        """
        Start with **SparkSession** as the entry point and say the **driver** owns planning and orchestration.
        Then explain that user code becomes a **logical plan**, **Catalyst** optimizes it, and Spark generates a
        **physical plan**. After that, the **DAG scheduler** splits work into **stages** at shuffle boundaries,
        and those stages are broken into **tasks** that run inside **executors** on worker nodes. Finally, mention
        that the biggest performance and failure topics are **shuffle**, **memory pressure**, **skew**, and
        **lineage-based recovery**.
        """
    )

    final_col1, final_col2 = st.columns(2, gap="large")
    with final_col1:
        st.info(
            """
            **When the interviewer asks "Why did the job fail?"**

            Usually answer in this order:
            1. memory pressure or skew
            2. shuffle spill or oversized partitions
            3. executor loss and task retries
            4. driver-side pressure
            5. streaming checkpoint or sink recovery issues
            """
        )

    with final_col2:
        st.success(
            """
            **When the interviewer asks "How do you optimize Spark?"**

            Usually answer in this order:
            1. reduce shuffle
            2. choose the right join strategy
            3. size partitions properly
            4. cache only reusable data
            5. use AQE, pushdown, and efficient storage formats
            """
        )


def render_pyspark() -> None:
    render_spark()
