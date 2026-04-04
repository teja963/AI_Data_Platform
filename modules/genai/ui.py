import pandas as pd
import streamlit as st


GENAI_STAGES = [
    {
        "key": "core",
        "title": "1. Core LLM + GenAI",
        "subtitle": "LLM foundations, transformer basics, RAG patterns, prompt engineering, and evaluation.",
        "theory": [
            "Understand the difference between the foundation model, the prompt layer, the retrieval layer, and the application layer.",
            "Know transformer basics well enough to explain tokens, embeddings, self-attention, context windows, and why latency rises with larger prompts.",
            "Treat RAG as a systems problem: ingestion, chunking, embeddings, retrieval, prompt assembly, generation, validation, and evaluation.",
            "Separate prompt engineering from prompt evaluation. A prompt that sounds good is not enough unless it is measurable on real tasks.",
        ],
        "practical": [
            "Build a document pipeline that chunks source files, creates embeddings, writes vectors, and stores metadata for filtering.",
            "Create prompt templates with system instructions, retrieved context, user question, formatting rules, and fallback behavior.",
            "Measure groundedness, retrieval hit rate, answer correctness, and latency instead of only checking whether the answer sounds fluent.",
            "Add retries, response schema validation, citations, and fallback flows for empty retrieval or low-confidence output.",
        ],
        "interview": [
            {
                "question": "What is the real architecture of a production RAG pipeline?",
                "answer": "Start from source ingestion, chunking, embedding, vector storage, retrieval, prompt construction, LLM inference, output validation, and evaluation. Mention metadata filters, observability, and feedback loops.",
            },
            {
                "question": "How is RAG different from fine-tuning?",
                "answer": "RAG injects fresh external context at query time. Fine-tuning changes model behavior or task specialization in weights. In production, teams often use RAG first because it is faster to refresh and safer to govern.",
            },
            {
                "question": "What metrics would you track for a GenAI application?",
                "answer": "Track retrieval hit rate, answer correctness, faithfulness or groundedness, latency, token cost, fallback rate, user feedback, and failure buckets such as empty retrieval or schema-validation errors.",
            },
            {
                "question": "Why do prompts fail in production even when demos look good?",
                "answer": "Prompt quality depends on retrieval quality, context length, ambiguity, and evaluation coverage. Demos hide edge cases like low-quality documents, conflicting sources, and missing guardrails.",
            },
        ],
    },
    {
        "key": "vector",
        "title": "2. Vector Databases",
        "subtitle": "Embeddings, indexing, metadata filters, Pinecone, Weaviate, and FAISS decision patterns.",
        "theory": [
            "A vector database is not just storage. It is retrieval latency, similarity search, metadata filtering, namespace strategy, and operational refresh design.",
            "Know the trade-off between managed services like Pinecone and self-managed or embedded options like FAISS.",
            "Understand why embedding model choice, chunk size, and metadata quality matter as much as the index itself.",
            "Be ready to explain approximate nearest neighbor behavior, filter-first vs retrieve-first logic, and why hybrid retrieval often improves enterprise search.",
        ],
        "practical": [
            "Design an ingestion path that creates embeddings, stores metadata, and supports re-embedding when the model or chunking strategy changes.",
            "Use namespaces or tenant keys for multi-tenant isolation and metadata filters for domain, document type, date, or access scope.",
            "Benchmark recall, latency, and cost under real top-k settings instead of testing only tiny demo data.",
            "Plan refresh and deletion behavior so stale documents do not survive forever in retrieval results.",
        ],
        "interview": [
            {
                "question": "When would you choose Pinecone over FAISS?",
                "answer": "Choose Pinecone when you want managed serving, operational simplicity, scaling, replication, and API-based production use. Choose FAISS when you want local control, lower-level experimentation, or embedded retrieval inside your own stack.",
            },
            {
                "question": "What are the biggest causes of bad retrieval?",
                "answer": "Poor chunking, weak metadata, wrong embedding model, missing filters, top-k tuned too low or too high, stale vectors, and relying on vector-only search when keyword signals matter.",
            },
            {
                "question": "How do you keep a vector store fresh?",
                "answer": "Use ingestion jobs for create and update events, tombstones or delete handling, re-embedding jobs after schema changes, and monitoring for drift between the source corpus and the vector index.",
            },
            {
                "question": "What does hybrid retrieval solve?",
                "answer": "Hybrid retrieval combines semantic similarity with lexical matching, which helps when exact keywords, IDs, error codes, or domain-specific phrases matter more than pure semantic closeness.",
            },
        ],
    },
    {
        "key": "frameworks",
        "title": "3. LLM Frameworks",
        "subtitle": "LangChain, LangGraph, tool calling, agents, orchestration, state, and observability.",
        "theory": [
            "LangChain is convenient for linear chains, retrievers, prompt templates, tool wrappers, and output parsers.",
            "LangGraph becomes valuable when the workflow has loops, branching, state transitions, retries, human approval, or multi-step agent behavior.",
            "Frameworks are orchestration layers, not the product itself. Strong system design still matters more than the library.",
            "Production GenAI stacks need traces, prompt versions, model versions, tool logs, and replayable execution state.",
        ],
        "practical": [
            "Use chains for predictable flows like classify -> retrieve -> answer -> validate.",
            "Use graphs when a run may revisit nodes, call multiple tools, wait for human approval, or switch behavior by intermediate state.",
            "Enforce structured outputs with schema validation so downstream systems are not broken by free-form text.",
            "Add tracing so every answer can be debugged through prompt, retrieved context, tool calls, and final model output.",
        ],
        "interview": [
            {
                "question": "When do you pick LangGraph over LangChain?",
                "answer": "Pick LangGraph when the workflow is stateful and nonlinear: loops, branching, retries, tool-driven state changes, or human-in-the-loop approval. Use LangChain for simpler linear orchestration.",
            },
            {
                "question": "How do you prevent agent workflows from becoming unreliable?",
                "answer": "Constrain tool scope, enforce structured outputs, keep state explicit, log every step, set timeouts and retry rules, and add fallback paths when tool calls fail.",
            },
            {
                "question": "What should be traced in an LLM framework?",
                "answer": "Trace prompts, model parameters, retrieved documents, tool inputs and outputs, latency, errors, and final responses. Without traces, debugging production behavior becomes guesswork.",
            },
            {
                "question": "Why is schema validation important in LLM apps?",
                "answer": "Because downstream systems need predictable output. Validation converts natural-language generation into something operationally safe and testable.",
            },
        ],
    },
    {
        "key": "mlops",
        "title": "4. ML Pipelines",
        "subtitle": "Kubeflow, MLflow, feature stores, evaluation loops, deployment controls, and feedback pipelines.",
        "theory": [
            "GenAI still needs MLOps. Retrieval quality, prompt quality, evaluation datasets, and deployment governance all require pipelines.",
            "MLflow is strong for experiment tracking, model registry, lineage, and packaging. Kubeflow is strong for orchestrated ML workflows and training pipelines.",
            "Feature stores matter when AI systems combine classical ML features, retrieval signals, user context, and online inference features.",
            "Evaluation should exist offline and online: benchmark datasets, shadow tests, user feedback, and regression tracking.",
        ],
        "practical": [
            "Track embedding versions, prompt versions, evaluator versions, and dataset snapshots the same way you track model versions.",
            "Create offline evaluation pipelines for faithfulness, relevance, answer correctness, and safety before production rollout.",
            "Use feature stores when serving-time features must match training-time definitions across systems.",
            "Build release flows with canary, shadow, rollback, and cost monitoring instead of replacing prompts or models blindly.",
        ],
        "interview": [
            {
                "question": "Why does a GenAI team still need MLflow or Kubeflow?",
                "answer": "Because prompts, embeddings, evaluation datasets, models, and pipelines all change over time. You need lineage, reproducibility, orchestration, and controlled releases, not only inference APIs.",
            },
            {
                "question": "Where does a feature store fit in an AI system?",
                "answer": "It fits when the final inference depends on user, product, behavioral, or operational features that must stay consistent across training and serving paths.",
            },
            {
                "question": "How do you evaluate a RAG system before production?",
                "answer": "Prepare a curated benchmark set, measure retrieval relevance and answer faithfulness, compare prompt and model variants, and define pass-fail thresholds before rollout.",
            },
            {
                "question": "What is the production release pattern for GenAI?",
                "answer": "Start with offline evaluation, then shadow or canary rollout, then monitor quality, latency, and cost, and keep rollback paths for prompts, retrievers, and models separately.",
            },
        ],
    },
    {
        "key": "cloud",
        "title": "5. AI Cloud Services",
        "subtitle": "AWS Bedrock, SageMaker, Vertex AI, governance, deployment, cost, and enterprise operating models.",
        "theory": [
            "Bedrock is strong for managed foundation model access, guardrails, and enterprise governance over hosted model APIs.",
            "SageMaker is broader for training, custom deployment, model management, pipelines, and endpoint operations.",
            "Vertex AI provides a similarly broad managed ML and GenAI platform on GCP, especially when the stack already leans GCP-native.",
            "Cloud choice is rarely only about the model. Governance, networking, data residency, IAM, cost visibility, and deployment control matter just as much.",
        ],
        "practical": [
            "Use Bedrock when you want managed FM access with less infrastructure burden and clear enterprise controls.",
            "Use SageMaker when you need custom training, fine-tuning, feature pipelines, or broader ML platform control on AWS.",
            "Use Vertex AI when your data and platform strategy already centers on GCP and you want integrated managed AI services.",
            "Always map the cloud choice to security, private networking, auditability, latency, and cost allocation before production commitment.",
        ],
        "interview": [
            {
                "question": "Bedrock vs SageMaker: how do you answer?",
                "answer": "Bedrock is the faster managed path for foundation model consumption and governance. SageMaker is the broader ML platform when you need training, custom hosting, pipelines, or deeper model lifecycle control.",
            },
            {
                "question": "What decides Vertex AI vs AWS AI services?",
                "answer": "Mostly the surrounding platform strategy: where the data lives, the existing cloud footprint, security controls, MLOps integrations, and the type of models and deployment patterns you need.",
            },
            {
                "question": "How do you control GenAI cost in the cloud?",
                "answer": "Track token usage, caching, prompt size, retrieval size, batch jobs, model selection, and fallback flows. Cost control is architectural, not only commercial.",
            },
            {
                "question": "What governance topics appear in enterprise GenAI interviews?",
                "answer": "PII handling, prompt logging policy, access control, tenant isolation, model approval, audit trails, private networking, and evaluation before exposure to end users.",
            },
        ],
    },
]


GENAI_SKILL_MATRIX = [
    {
        "Stage": "Foundation",
        "Skill Focus": "Python, APIs, data pipelines, orchestration, embeddings basics",
        "What You Should Be Able To Build": "A document ingestion job that prepares chunked text and metadata for retrieval.",
    },
    {
        "Stage": "RAG Builder",
        "Skill Focus": "Chunking, embeddings, vector search, prompt templates, evaluation",
        "What You Should Be Able To Build": "A grounded RAG assistant with citations, fallback handling, and measurable quality.",
    },
    {
        "Stage": "LLM Application Engineer",
        "Skill Focus": "Framework orchestration, tools, state, structured outputs, tracing",
        "What You Should Be Able To Build": "A workflow that retrieves, calls tools, validates outputs, and handles retries safely.",
    },
    {
        "Stage": "AI Platform Engineer",
        "Skill Focus": "MLflow, Kubeflow, feature store, deployment controls, evaluation pipelines",
        "What You Should Be Able To Build": "A repeatable release process for prompts, retrievers, and models with rollback and lineage.",
    },
    {
        "Stage": "Enterprise GenAI Engineer",
        "Skill Focus": "Bedrock/SageMaker/Vertex AI, governance, security, cost, observability",
        "What You Should Be Able To Build": "A production-ready AI platform with access control, monitoring, and interview-grade system design depth.",
    },
]


INTERVIEW_PLAYBOOK = [
    {
        "topic": "RAG System Design",
        "strong_answer": "Explain ingestion, chunking, embeddings, vector DB, retrieval, reranking, prompt assembly, LLM inference, validation, evaluation, and feedback loops in that order.",
    },
    {
        "topic": "Latency And Cost",
        "strong_answer": "Break latency into retrieval, prompt construction, model inference, and post-processing. Break cost into embeddings, storage, token usage, and online traffic volume.",
    },
    {
        "topic": "Failure Handling",
        "strong_answer": "Cover empty retrieval, stale vectors, low-confidence answers, tool failures, timeouts, malformed output, and governance blocks. Then explain your fallback strategy.",
    },
    {
        "topic": "Evaluation",
        "strong_answer": "Always mention offline benchmark sets plus online feedback. Distinguish retrieval metrics from generation metrics instead of collapsing them into one score.",
    },
    {
        "topic": "Security And Governance",
        "strong_answer": "Talk about prompt logging policy, PII masking, tenant isolation, access control, document-level authorization, and audit trails.",
    },
]


def build_box(title, lines=None, active=False, accent="blue", min_height=58):
    # Move from hardcoded hex values to CSS classes for consistent dark-mode support
    class_name = "genai-box"
    if active:
        class_name += f" active-{accent}"

    details = lines or []
    if isinstance(details, str):
        details = [details]
    body = "".join(
        f"<div style='font-size:10px;line-height:1.2;margin-top:3px;opacity:0.8;color:inherit;'>{line}</div>"
        for line in details
    )
    return (
        f"<div class='{class_name}' style='padding:8px;min-height:{min_height}px;text-align:center;'>"
        f"<div style='font-size:12px;font-weight:700;color:inherit;'>{title}</div>{body}</div>"
    )


def render_stage_cards():
    st.subheader("Five-Stage Roadmap")
    columns = st.columns(5)
    for idx, stage in enumerate(GENAI_STAGES):
        with columns[idx]:
            st.markdown(
                (
                    "<div class='roadmap-card' style='padding:12px;min-height:160px;'>"
                    f"<div style='font-weight:700;margin-bottom:8px;color:inherit;'>{stage['title']}</div>"
                    f"<div style='font-size:13px;opacity:0.8;color:inherit;'>{stage['subtitle']}</div>"
                    "</div>"
                ),
                unsafe_allow_html=True,
            )


def render_rag_simulator():
    st.markdown("### RAG Architecture Simulator")
    control_col1, control_col2, control_col3, control_col4 = st.columns(4)
    retrieval_mode = control_col1.selectbox("Retrieval", ["Vector Only", "Hybrid", "Hybrid + Rerank"], key="genai_rag_retrieval")
    chunk_strategy = control_col2.selectbox("Chunking", ["Small", "Balanced", "Large"], key="genai_rag_chunking")
    prompt_mode = control_col3.selectbox("Prompt Style", ["Simple QA", "Guarded QA", "Structured Output"], key="genai_rag_prompt")
    evaluation_mode = control_col4.selectbox("Evaluation", ["Offline Only", "Offline + Online", "Full Eval + Feedback"], key="genai_rag_eval")

    diagram = (
        "<div style='display:grid;grid-template-columns:repeat(8,minmax(90px,1fr));gap:8px;'>"
        + build_box("Sources", ["PDFs", "Docs", "Logs"])
        + build_box("Ingestion", ["parse", "clean"])
        + build_box("Chunking", [chunk_strategy], active=True, accent="blue")
        + build_box("Embeddings", ["embed", "version"])
        + build_box("Vector DB", ["metadata", "filters"], active=retrieval_mode != "Vector Only", accent="green")
        + build_box("Retriever", [retrieval_mode], active=True, accent="blue")
        + build_box("Prompt", [prompt_mode], active=True, accent="amber")
        + build_box("Evals", [evaluation_mode], active=evaluation_mode != "Offline Only", accent="green")
        + "</div>"
    )
    st.markdown(diagram, unsafe_allow_html=True)

    st.markdown("#### What This Configuration Teaches")
    if retrieval_mode == "Vector Only":
        st.markdown("- Use this for simple semantic lookup, but mention weaker keyword matching in interviews.")
    elif retrieval_mode == "Hybrid":
        st.markdown("- Hybrid retrieval is usually the safer production answer because exact keywords and semantic recall both matter.")
    else:
        st.markdown("- Hybrid + rerank is the stronger enterprise answer when relevance quality matters more than the smallest latency.")

    if chunk_strategy == "Small":
        st.markdown("- Smaller chunks improve precision but can lose broader context.")
    elif chunk_strategy == "Balanced":
        st.markdown("- Balanced chunking is the default interview answer unless the corpus has very unusual structure.")
    else:
        st.markdown("- Large chunks preserve context but increase prompt size and dilute retrieval precision.")

    if prompt_mode == "Structured Output":
        st.markdown("- Structured output is the best answer when the LLM response feeds another system or UI workflow.")

    if evaluation_mode == "Full Eval + Feedback":
        st.markdown("- This is the strongest production answer because it covers offline testing plus live user feedback loops.")


def render_vector_selector():
    st.markdown("### Vector Store Decision Lab")
    col1, col2, col3 = st.columns(3)
    data_scale = col1.selectbox("Corpus Scale", ["Prototype", "Mid-size Production", "Large Enterprise"], key="genai_vector_scale")
    ops_model = col2.selectbox("Operating Model", ["Fully Managed", "Self Managed", "Local / Embedded"], key="genai_vector_ops")
    query_pattern = col3.selectbox("Query Pattern", ["Semantic Only", "Metadata Heavy", "Hybrid Search"], key="genai_vector_query")

    pinecone_active = ops_model == "Fully Managed"
    faiss_active = ops_model == "Local / Embedded"
    weaviate_active = query_pattern in {"Metadata Heavy", "Hybrid Search"} or ops_model == "Self Managed"

    st.markdown(
        "<div style='display:grid;grid-template-columns:repeat(3,minmax(120px,1fr));gap:8px;'>"
        + build_box("Pinecone", ["managed serving", "ops simplicity"], active=pinecone_active, accent="blue", min_height=72)
        + build_box("Weaviate", ["filters", "hybrid search"], active=weaviate_active, accent="green", min_height=72)
        + build_box("FAISS", ["local speed", "DIY ops"], active=faiss_active, accent="amber", min_height=72)
        + "</div>",
        unsafe_allow_html=True,
    )

    st.markdown("#### Interview Guidance")
    if pinecone_active:
        st.markdown("- Say Pinecone when the team wants managed operations, fast onboarding, and fewer infrastructure responsibilities.")
    if weaviate_active:
        st.markdown("- Say Weaviate when metadata filters, hybrid retrieval, or self-managed flexibility are central.")
    if faiss_active:
        st.markdown("- Say FAISS when the system is embedded, experimental, or locally controlled rather than platform-managed.")
    if data_scale == "Large Enterprise":
        st.markdown("- At enterprise scale, talk about refresh pipelines, delete handling, re-embedding, and tenant isolation, not only vector search speed.")


def render_framework_selector():
    st.markdown("### LLM Framework Decision Lab")
    col1, col2, col3 = st.columns(3)
    workflow_shape = col1.selectbox("Workflow Shape", ["Linear Chain", "Branching", "Looping / Stateful"], key="genai_framework_shape")
    tool_usage = col2.selectbox("Tool Usage", ["Low", "Moderate", "High"], key="genai_framework_tools")
    human_gate = col3.selectbox("Human Approval", ["Not Needed", "Occasional", "Required"], key="genai_framework_human")

    langchain_active = workflow_shape == "Linear Chain"
    langgraph_active = workflow_shape in {"Branching", "Looping / Stateful"} or human_gate != "Not Needed" or tool_usage == "High"

    st.markdown(
        "<div style='display:grid;grid-template-columns:repeat(2,minmax(140px,1fr));gap:8px;'>"
        + build_box("LangChain", ["chains", "retrievers", "prompt templates"], active=langchain_active, accent="blue", min_height=78)
        + build_box("LangGraph", ["state", "branches", "loops", "human-in-loop"], active=langgraph_active, accent="green", min_height=78)
        + "</div>",
        unsafe_allow_html=True,
    )

    st.markdown("#### Interview Guidance")
    st.markdown("- Explain LangChain as the fast path for predictable chains and LangGraph as the answer for stateful agent workflows.")
    if langgraph_active:
        st.markdown("- Because your selected workflow is not purely linear, LangGraph is the stronger answer here.")


def render_pipeline_selector():
    st.markdown("### ML Pipeline Operating Model")
    col1, col2, col3 = st.columns(3)
    experimentation = col1.selectbox("Experiment Tracking", ["Lightweight", "Heavy"], key="genai_mlops_tracking")
    deployment = col2.selectbox("Deployment Control", ["Simple Releases", "Canary + Rollback"], key="genai_mlops_release")
    features = col3.selectbox("Serving Features", ["Prompt + Retrieval Only", "Feature-Rich Online Serving"], key="genai_mlops_features")

    mlflow_active = experimentation == "Heavy" or deployment == "Canary + Rollback"
    kubeflow_active = deployment == "Canary + Rollback"
    feature_store_active = features == "Feature-Rich Online Serving"

    st.markdown(
        "<div style='display:grid;grid-template-columns:repeat(3,minmax(120px,1fr));gap:8px;'>"
        + build_box("MLflow", ["experiments", "registry", "lineage"], active=mlflow_active, accent="blue", min_height=76)
        + build_box("Kubeflow", ["training pipelines", "release control"], active=kubeflow_active, accent="green", min_height=76)
        + build_box("Feature Store", ["online/offline parity"], active=feature_store_active, accent="amber", min_height=76)
        + "</div>",
        unsafe_allow_html=True,
    )

    st.markdown("#### Interview Guidance")
    st.markdown("- For AI data engineer roles, always connect GenAI back to lineage, orchestration, evaluation datasets, and repeatable release flows.")
    if feature_store_active:
        st.markdown("- A feature store matters when the answer depends on user, product, or operational features beyond retrieved documents.")


def render_cloud_selector():
    st.markdown("### Cloud Service Selector")
    col1, col2, col3 = st.columns(3)
    model_path = col1.selectbox("Model Strategy", ["Managed Foundation Models", "Custom Training / Fine-Tuning"], key="genai_cloud_model")
    governance = col2.selectbox("Governance Need", ["Standard", "Strict Enterprise"], key="genai_cloud_governance")
    cloud_preference = col3.selectbox("Cloud Footprint", ["AWS First", "GCP First", "Mixed"], key="genai_cloud_pref")

    bedrock_active = model_path == "Managed Foundation Models" and cloud_preference in {"AWS First", "Mixed"}
    sagemaker_active = model_path == "Custom Training / Fine-Tuning" and cloud_preference in {"AWS First", "Mixed"}
    vertex_active = cloud_preference == "GCP First"

    st.markdown(
        "<div style='display:grid;grid-template-columns:repeat(3,minmax(120px,1fr));gap:8px;'>"
        + build_box("AWS Bedrock", ["managed FM access", "guardrails"], active=bedrock_active, accent="blue", min_height=76)
        + build_box("SageMaker", ["training", "deployment", "ML platform"], active=sagemaker_active, accent="green", min_height=76)
        + build_box("Vertex AI", ["managed AI on GCP"], active=vertex_active, accent="amber", min_height=76)
        + "</div>",
        unsafe_allow_html=True,
    )

    st.markdown("#### Interview Guidance")
    if governance == "Strict Enterprise":
        st.markdown("- Mention IAM, networking, audit trails, private connectivity, and approval workflows as part of the service choice.")
    st.markdown("- The strongest answer connects service choice to data location, governance, release control, and operating model, not only model availability.")


def render_stage_detail(stage):
    st.subheader(stage["title"])
    st.caption(stage["subtitle"])

    if stage["key"] == "core":
        render_rag_simulator()
    elif stage["key"] == "vector":
        render_vector_selector()
    elif stage["key"] == "frameworks":
        render_framework_selector()
    elif stage["key"] == "mlops":
        render_pipeline_selector()
    else:
        render_cloud_selector()

    theory_tab, practical_tab, interview_tab = st.tabs(["Theory", "Practical", "Interview"])

    with theory_tab:
        for item in stage["theory"]:
            st.markdown(f"- {item}")

    with practical_tab:
        for item in stage["practical"]:
            st.markdown(f"- {item}")

    with interview_tab:
        for item in stage["interview"]:
            with st.container(border=True):
                st.markdown(f"**Question**: {item['question']}")
                st.markdown(f"**Strong Answer Direction**: {item['answer']}")


def render_roadmap_tab():
    st.title("GenAI Engineering Dashboard")
    st.write(
        "This section is built as an interview and implementation roadmap for moving from data engineering foundations into full GenAI engineering."
    )
    st.info(
        "Treat theory as the architectural vocabulary and practical work as the operating model. Strong interview answers need both."
    )

    render_stage_cards()

    st.subheader("Skill Ladder: Data Engineer -> AI Data Engineer")
    st.dataframe(pd.DataFrame(GENAI_SKILL_MATRIX), use_container_width=True, hide_index=True)

    st.subheader("What A Strong AI Data Engineer Can Explain End To End")
    checklist = [
        "How documents are ingested, chunked, embedded, stored, retrieved, and refreshed.",
        "How prompts, tools, frameworks, and evaluators fit into the application workflow.",
        "How latency, cost, governance, and feedback loops shape production architecture.",
        "How Kubeflow, MLflow, feature stores, and cloud services support release quality and reliability.",
        "How to answer system-design and troubleshooting questions with concrete trade-offs rather than tool names only.",
    ]
    for item in checklist:
        st.markdown(f"- {item}")


def render_stage_labs_tab():
    stage_tabs = st.tabs([stage["title"] for stage in GENAI_STAGES])
    for tab, stage in zip(stage_tabs, GENAI_STAGES):
        with tab:
            render_stage_detail(stage)


def render_interview_tab():
    st.title("GenAI Interview Playbook")
    st.write(
        "Use this as the answer structure for AI data engineer and GenAI platform interviews. The goal is not only naming tools, but explaining architecture, trade-offs, and production behavior."
    )

    st.subheader("High-Value Interview Themes")
    st.dataframe(pd.DataFrame(INTERVIEW_PLAYBOOK), use_container_width=True, hide_index=True)

    st.subheader("Answer Framework For System Design Questions")
    steps = [
        "Start with the business problem, user type, and freshness or latency expectation.",
        "Explain the ingestion path and where chunking, embedding, indexing, and metadata enrichment happen.",
        "Explain retrieval, prompt assembly, model invocation, validation, and fallback behavior.",
        "Explain evaluation, observability, feedback loops, rollout strategy, and rollback strategy.",
        "Close with security, governance, tenant isolation, and cost control.",
    ]
    for item in steps:
        st.markdown(f"- {item}")

    st.subheader("Common Failure Scenarios You Should Be Ready To Explain")
    failures = [
        "Good model, bad retrieval: embeddings are stale, chunking is poor, or metadata filters are wrong.",
        "Good retrieval, bad answer: prompt is weak, context window is overloaded, or the model is not constrained enough.",
        "High latency: retrieval is slow, prompts are too large, or the model tier is oversized for the use case.",
        "High cost: prompt inflation, excessive top-k, repeated embeddings, or no response caching.",
        "Enterprise rejection: missing governance, poor logging policy, weak access control, or no evaluation evidence.",
    ]
    for item in failures:
        st.markdown(f"- {item}")


def render_genai():
    roadmap_tab, stages_tab, interview_tab = st.tabs(["Roadmap", "Stage Labs", "Interview Prep"])

    with roadmap_tab:
        render_roadmap_tab()

    with stages_tab:
        render_stage_labs_tab()

    with interview_tab:
        render_interview_tab()
