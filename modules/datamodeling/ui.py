import streamlit as st
import pandas as pd
from core.ai import ask_ai
import random
from datetime import datetime

# =========================================================
# 🔹 ENTRY POINT
# =========================================================

def render_datamodeling():

    render_title("📊 Data Modelling")

    tab_labels = [
        "Fundamentals",
        "Dimensional Modeling",
        "Architecture",
        "Distributed",
        "Interview Mode"
    ]

    # =====================================================
    # 🔥 STEP 1: READ FROM URL
    # =====================================================
    query_params = st.query_params

    selected = query_params.get("dm_tab", "Fundamentals")

    if selected not in tab_labels:
        selected = "Fundamentals"

    # =====================================================
    # 🔥 STEP 2: TAB-LIKE UI (REPLACES st.tabs)
    # =====================================================
    selected_tab = st.radio(
        "",
        tab_labels,
        index=tab_labels.index(selected),
        horizontal=True
    )

    # =====================================================
    # 🔥 STEP 3: UPDATE URL (CRITICAL)
    # =====================================================
    st.query_params["dm_tab"] = selected_tab

    # =====================================================
    # 🔥 STEP 4: RENDER CONTENT (NOW WORKS PERFECTLY)
    # =====================================================
    if selected_tab == "Fundamentals":
        show_fundamentals()

    elif selected_tab == "Dimensional Modeling":
        show_dimensional_modeling()

    elif selected_tab == "Architecture":
        show_architecture()

    elif selected_tab == "Distributed":
        show_distributed_modeling()

    elif selected_tab == "Interview Mode":
        show_interview_mode()


# =========================================================
# 🔹 UI COMPONENTS (FULL CONTROL)
# =========================================================

def render_title(text):
    st.markdown(f"<h2>{text}</h2>", unsafe_allow_html=True)

def render_subtitle(text):
    st.markdown(f"<h4 style='margin-top:20px'>{text}</h4>", unsafe_allow_html=True)

def render_box(text, color="#E8F4FD"):
    st.markdown(
        f"<div style='padding:12px;border-radius:8px;background:{color};margin-bottom:10px'>{text}</div>",
        unsafe_allow_html=True
    )

def render_df(data, columns):
    df = pd.DataFrame(data, columns=columns)
    st.dataframe(df, use_container_width=True, hide_index=True)

def render_side_by_side(title1, data1, title2, data2, columns):
    col1, col2 = st.columns(2)

    with col1:
        render_subtitle(title1)
        render_df(data1, columns)

    with col2:
        render_subtitle(title2)
        render_df(data2, columns)

def render_code(text):
    st.markdown(f"<pre>{text}</pre>", unsafe_allow_html=True)


# =========================================================
# 🔹 AI PROMPT (STRONG - FAANG LEVEL)
# =========================================================

def render_ai_chat(section_key, title, topic):
    import streamlit as st
    from core.ai import ask_ai

    st.markdown("---")
    st.markdown(f"### 💬 {title}")

    chat_key = f"{section_key}_chat"
    input_key = f"{section_key}_chat_input"   # ✅ UNIQUE KEY

    if chat_key not in st.session_state:
        st.session_state[chat_key] = []

    # Display chat history
    for chat in st.session_state[chat_key]:
        if chat["role"] == "user":
            with st.chat_message("user"):
                st.markdown(chat["content"])
        else:
            with st.chat_message("assistant"):
                st.markdown(chat["content"])

    # ✅ FIXED HERE
    user_input = st.chat_input("Ask anything...", key=input_key)

    if user_input:
        st.session_state[chat_key].append({
            "role": "user",
            "content": user_input
        })

        with st.chat_message("user"):
            st.markdown(user_input)

        prompt = f"""
            You are a senior data engineer at Amazon, Google, or Microsoft.

            Answer the following question on {topic}.

            Question:
            {user_input}

            Requirements:
            - Clear and well-detailed structured answer
            - Must include at least 2 real-world examples (different domains if possible)
            - Provide interview-ready explanation with reasoning
            - Include edge cases, trade-offs, or pitfalls if applicable
            - Use bullet points for clarity
            - Keep explanation concise but insightful (avoid unnecessary verbosity)
            - If applicable, include schema/table examples
            - Avoid generic textbook answers — make it practical and scenario-driven

            Format:
            - Definition (if applicable)
            - Explanation
            - Real-world examples
            - Edge cases / interview insights
            """

        response = ask_ai(prompt)

        st.session_state[chat_key].append({
            "role": "assistant",
            "content": response
        })

        with st.chat_message("assistant"):
            st.markdown(response)

# =========================================================
# 🔹 FUNDAMENTALS
# =========================================================

def show_fundamentals():
    render_title("📘 Data Modeling Fundamentals")

    render_box("""
    Data Modeling = Structuring data to answer business questions efficiently.
    Connects business logic → database schema.
    """)

    render_box("""
    Example:
    Customer → customers  
    Orders → orders  
    Products → products  
    """)

    tab1, tab2, tab3 = st.tabs([
        "Normalization",
        "OLTP vs OLAP",
        "ER Modeling"
    ])

    # =====================================================
    # 🔴 NORMALIZATION
    # =====================================================
    with tab1:
        render_title("Normalization (UNF → BCNF)")

        # ---------------- UNF → 1NF ----------------
        render_subtitle("UNF → 1NF")

        render_side_by_side(
            "❌ Before (UNF)",
            [["101", "John", "DB, ML"], ["102", "Mike", "AI"]],
            "✅ After (1NF)",
            [["101", "John", "DB"], ["101", "John", "ML"], ["102", "Mike", "AI"]],
            ["student_id", "name", "course"]
        )

        render_box("❌ Problem: Multiple values in one column", "#FDECEA")
        render_box("✅ Fix: Split rows into atomic values", "#E6F4EA")

        # ---------------- 1NF → 2NF ----------------
        render_subtitle("1NF → 2NF")

        col1, col2 = st.columns(2)

        with col1:
            render_subtitle("❌ Before")
            render_df(
                [["101", "DB", "John"], ["101", "ML", "John"]],
                ["student_id", "course", "student_name"]
            )
            render_box("Partial dependency: name depends only on student_id", "#FDECEA")

        with col2:
            render_subtitle("✅ After")

            st.markdown("**Students Table**")
            render_df(
                [["101", "John"]],
                ["student_id", "student_name"]
            )

            st.markdown("**Student_Course Table**")
            render_df(
                [["101", "DB"], ["101", "ML"]],
                ["student_id", "course"]
            )

            render_box("Removed partial dependency", "#E6F4EA")

        # ---------------- 2NF → 3NF ----------------
        render_subtitle("2NF → 3NF")

        col1, col2 = st.columns(2)

        with col1:
            render_subtitle("❌ Before")
            render_df(
                [["DB", "Smith", "Computer"]],
                ["course", "instructor", "department"]
            )
            render_box("Transitive dependency: course → instructor → department", "#FDECEA")

        with col2:
            render_subtitle("✅ After")

            st.markdown("**Course Table**")
            render_df(
                [["DB", "Smith"]],
                ["course", "instructor"]
            )

            st.markdown("**Instructor Table**")
            render_df(
                [["Smith", "Computer"]],
                ["instructor", "department"]
            )

            render_box("Removed transitive dependency", "#E6F4EA")

        # ---------------- 3NF → BCNF ----------------
        render_subtitle("3NF → BCNF")

        col1, col2 = st.columns(2)

        with col1:
            render_subtitle("❌ Before")
            render_df(
                [["Smith", "DB"], ["Smith", "ML"]],
                ["instructor", "course"]
            )
            render_box("Instructor determines course (not a candidate key)", "#FDECEA")

        with col2:
            render_subtitle("✅ After")

            render_df(
                [["Smith", "DB"], ["Smith", "ML"]],
                ["instructor", "course"]
            )

            render_box("Ensured determinant is candidate key", "#E6F4EA")

        # ---------------- MEMORY ----------------
        render_box("""
        🧠 Memory:
        1NF → Atomic  
        2NF → No Partial  
        3NF → No Transitive  
        BCNF → Strong Keys  
        """, "#E8F4FD")

        # ---------------- AI ----------------
        st.markdown("---")

        render_ai_chat(
                section_key="normalization",
                title="Ask about Normalization (1NF, 2NF, 3NF, BCNF)",
                topic="Data Modeling Normalization"
            )

    # =====================================================
    # 🟢 OLTP vs OLAP
    # =====================================================
    with tab2:
        render_title("OLTP vs OLAP")

        render_df([
            ["Purpose", "Run operations", "Analyze data"],
            ["Schema", "Normalized (3NF)", "Denormalized (Star Schema)"],
            ["Query", "Point lookup", "Aggregation"],
            ["Data Volume", "Current", "Historical"],
            ["Latency", "Low", "High"],
            ["Tech Stack", "MySQL, PostgreSQL", "StarRocks, BigQuery"],
        ], ["Aspect", "OLTP", "OLAP"])

        render_box("""
        Example:
        Swiggy order placement → OLTP  
        Monthly analytics dashboard → OLAP  
        """, "#E6F4EA")

        render_box("""
        🧠 Mnemonic:
        OLTP → Run business  
        OLAP → Analyze business  
        """, "#E8F4FD")

        st.markdown("---")

        render_ai_chat(
            section_key="oltp_olap",
            title="Ask about OLTP vs OLAP",
            topic="OLTP vs OLAP systems in real-world data engineering"
        )

    # =====================================================
    # 🔵 ER MODELING
    # =====================================================
    with tab3:
        render_title("ER Modeling")

        # =====================================================
        # 🔹 CONCEPTS (CARD UI)
        # =====================================================
        st.markdown("""
        <table style="width:100%; border-spacing:10px;">
            <tr>
                <td style="padding:10px; background:#E8F4FD; border-radius:8px;">
                    <b>Entity</b><br>Real-world object (Customer, Order)
                </td>
                <td style="padding:10px; background:#E6F4EA; border-radius:8px;">
                    <b>Attribute</b><br>Properties (name, id)
                </td>
                <td style="padding:10px; background:#FFF4E5; border-radius:8px;">
                    <b>Relationship</b><br>Connection between entities
                </td>
            </tr>
        </table>
        """, unsafe_allow_html=True)

        # =====================================================
        # 🔹 VISUAL DIAGRAM
        # =====================================================
        render_subtitle("Visual ER Diagram")

        st.markdown("""
        <table style="width:100%; text-align:center; margin:20px 0;">
            <tr>
                <td style="padding:15px; border:2px solid #4CAF50; border-radius:10px;">
                    <b>Customer</b><br>id<br>name
                </td>
                <td style="font-size:18px;">➜ places ➜</td>
                <td style="padding:15px; border:2px solid #2196F3; border-radius:10px;">
                    <b>Order</b><br>order_id<br>amount
                </td>
            </tr>
        </table>
        """, unsafe_allow_html=True)

        st.markdown("""
        <div style="padding:10px; background:#E8F4FD; border-radius:8px;">
        Customer places Orders (1:M relationship)
        </div>
        """, unsafe_allow_html=True)

        # =====================================================
        # 🔹 CARDINALITY
        # =====================================================
        render_subtitle("Cardinality")

        st.markdown("""
        <table style="width:100%; text-align:center;">
            <tr>
                <td style="padding:10px; background:#FDECEA; border-radius:8px;">
                    1 : 1 → One to One
                </td>
                <td style="padding:10px; background:#E6F4EA; border-radius:8px;">
                    1 : M → One to Many
                </td>
                <td style="padding:10px; background:#FFF4E5; border-radius:8px;">
                    M : N → Many to Many
                </td>
            </tr>
        </table>
        """, unsafe_allow_html=True)

        # =====================================================
        # 🔹 MANY-TO-MANY EXAMPLE
        # =====================================================
        render_subtitle("Many-to-Many Example")

        st.markdown("""
        <table style="width:100%; text-align:center; margin:20px 0;">
            <tr>
                <td style="padding:15px; border:2px solid #FF9800; border-radius:10px;">
                    <b>Student</b>
                </td>
                <td style="font-size:18px;">⇄ enrolls ⇄</td>
                <td style="padding:15px; border:2px solid #9C27B0; border-radius:10px;">
                    <b>Course</b>
                </td>
            </tr>
        </table>
        """, unsafe_allow_html=True)

        st.markdown("""
        <div style="padding:10px; background:#E6F4EA; border-radius:8px;">
        Resolved using bridge table (student_course)
        </div>
        """, unsafe_allow_html=True)

        # =====================================================
        # 🔹 TABLE MAPPING
        # =====================================================
        render_subtitle("Mapping ER → Tables")

        render_df(
            [
                ["students", "id, name"],
                ["courses", "id, title"],
                ["student_course", "student_id, course_id"]
            ],
            ["Table", "Columns"]
        )

        st.markdown("""
        <div style="padding:10px; background:#E8F4FD; border-radius:8px;">
        🔥 Key Insight: M:N relationships are always broken into bridge tables.
        </div>
        """, unsafe_allow_html=True)

        # =====================================================
        # 🔹 REAL-WORLD EXAMPLE
        # =====================================================
        render_subtitle("Real-world Example")

        st.markdown("""
        <div style="padding:12px; background:#E6F4EA; border-radius:8px;">
        <b>Netflix Example</b><br><br>

        - Users watch movies  
        - One user → many movies  
        - Many users → same movie  

        👉 M:N relationship → needs bridge table
        </div>
        """, unsafe_allow_html=True)

        # =====================================================
        # 🔹 AI QUESTIONS (UNCHANGED QUALITY)
        # =====================================================
        st.markdown("---")

        render_ai_chat(
            section_key="er_modeling",
            title="Ask about ER Modeling",
            topic="Entity Relationship Modeling and schema design"
        )

# =========================================================
# 2. DIMENSIONAL MODELING 
# =========================================================
def show_dimensional_modeling():
    
    st.header("Dimensional Modeling")
    # =====================================================
    # 🔹 FACT vs DIMENSION
    # =====================================================

    st.markdown("### 🔥 Fact vs Dimension")

    df_compare = pd.DataFrame([
        ["Definition", "Stores measurable metrics for analysis", "Stores descriptive attributes for context"],
        ["Purpose", "Used for aggregations (SUM, COUNT)", "Used for filtering & grouping"],
        ["Data Type", "Numeric values", "Text / categorical"],
        ["Keys", "Contains foreign keys", "Contains primary keys"],
        ["Example", "sales_amt, quantity", "customer_name, city"]
    ], columns=["Aspect", "Fact Table", "Dimension Table"])

    st.dataframe(df_compare, use_container_width=True, hide_index=True)

    # ---------------- EXAMPLE TABLES ----------------
    st.markdown("### 📊 Example Tables")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Fact Table: Sales_Fact**")
        df_fact = pd.DataFrame([
            ["20240101", "P101", "C201", "500"],
            ["20240102", "P102", "C202", "300"]
        ], columns=["date_id", "product_id", "customer_id", "sales_amt"])

        st.dataframe(df_fact, hide_index=True)

    with col2:
        st.markdown("**Dimension Table: Customer_Dim**")
        df_dim = pd.DataFrame([
            ["C201", "John", "Bangalore"],
            ["C202", "Mike", "Chennai"]
        ], columns=["customer_id", "name", "city"])

        st.dataframe(df_dim, hide_index=True)

    # ---------------- VISUAL DIAGRAM ----------------
    st.markdown("### 🔷 Relationship Diagram")

    col_left, col_center, col_right = st.columns([1,2,1])

    with col_center:
        st.markdown("**⬆️ Dimensions connect to Fact**")

        c1, c2, c3 = st.columns(3)

        with c1:
            st.info("Customer_dim")
            st.info("Product_dim")

        with c2:
            st.success("Sales_Fact\n(Metrics)")

        with c3:
            st.info("Date_dim")
            st.info("Store_dim")

    # =====================================================
    # 🔹 GRAIN (VISUAL + STRUCTURED)
    # =====================================================

    # ---------------- DEFINITION TABLE ----------------
    st.markdown("### 🔥 Grain Definition")

    df_grain_def = pd.DataFrame([
        ["Definition", "Grain defines what a single row in a fact table represents"],
        ["Purpose", "Ensures correct level of detail for analysis"],
        ["Impact", "Directly affects aggregation and query results"]
    ], columns=["Aspect", "Explanation"])

    st.dataframe(df_grain_def, use_container_width=True, hide_index=True)

    # ---------------- EXAMPLES ----------------
    st.markdown("### 📊 Grain Examples (Real-world)")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Transaction Grain (Correct - Detailed)**")

        df_txn = pd.DataFrame([
            ["1001", "iPhone", "800"],
            ["1002", "Laptop", "1200"]
        ], columns=["order_id", "product", "amount"])

        st.dataframe(df_txn, hide_index=True)

    with col2:
        st.markdown("**Daily Grain (Aggregated - Less Detail)**")

        df_daily = pd.DataFrame([
            ["2024-01-01", "5000"],
            ["2024-01-02", "7000"]
        ], columns=["date", "total_sales"])

        st.dataframe(df_daily, hide_index=True)

    # ---------------- VISUAL FLOW ----------------
    st.markdown("### 🔷 Grain Selection Flow")

    c1, c2, c3 = st.columns(3)

    with c1:
        st.info("Raw Data\n(Transactions)")

    with c2:
        st.warning("Choose Grain\n(Level of Detail)")

    with c3:
        st.success("Fact Table\n(Final Structure)")

    # ---------------- WHY IMPORTANT ----------------
    st.markdown("### 🚨 Why Grain is Critical")

    df_importance = pd.DataFrame([
        ["Wrong Grain", "Leads to incorrect aggregations"],
        ["Too High Level", "Loss of detailed insights"],
        ["Too Low Level", "Heavy queries, performance issues"],
        ["Correct Grain", "Accurate + efficient analytics"]
    ], columns=["Scenario", "Impact"])

    st.dataframe(df_importance, use_container_width=True, hide_index=True)
  
# =========================================================
# 3. DATA WAREHOUSE ARCHITECTURE
# =========================================================
def show_architecture():
    st.header("Data Warehouse Architecture")

    st.markdown("""
    Layers:

    1. Source Systems  
    2. Staging Layer  
    3. Core Warehouse  
    4. Data Marts  
    5. BI / Analytics  
    """)

    st.subheader("Lakehouse")

    st.markdown("""
    - Combines Data Lake + Warehouse  
    - Supports batch + streaming  
    - ACID transactions  
    """)

    st.subheader("Why Lakehouse")

    st.table([
        ["Problem", "Solution"],
        ["Data duplication", "Single storage"],
        ["No schema control", "Schema enforcement"]
    ])


# =========================================================
# 4. DISTRIBUTED MODELING (your page 7.7)
# =========================================================
def show_distributed_modeling():
    st.header("Distributed Data Modeling")

    topic = st.selectbox("Choose Topic", [
        "Data Locality",
        "Distributed Joins",
        "Consistent Hashing",
        "Data Skew"
    ])

    if topic == "Data Locality":
        st.write("Move compute to data")

    elif topic == "Distributed Joins":
        st.write("Broadcast vs Shuffle joins")

    elif topic == "Consistent Hashing":
        st.write("Minimize reshuffling of data")

    elif topic == "Data Skew":
        st.write("Uneven data distribution problem")


# =========================================================
# 5. INTERVIEW MODE (STEP 3)
# =========================================================
def show_interview_mode():
    st.header("Interview Mode")

    if "dm_question" not in st.session_state:
        st.session_state.dm_question = None

    if st.button("Generate Question"):
        st.session_state.dm_question = ask_ai(
            "Ask a data modelling interview question"
        )

    if st.session_state.dm_question:
        st.write(st.session_state.dm_question)

        answer = st.text_area("Your Answer")

        if st.button("Evaluate"):
            feedback = ask_ai(f"""
            Question: {st.session_state.dm_question}
            Answer: {answer}

            Evaluate and give score out of 10.
            """)
            st.write(feedback)