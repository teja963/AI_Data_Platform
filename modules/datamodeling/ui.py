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

    tab1, tab2, tab3 = st.tabs([
        "Core Concepts",
        "Schemas & Dimensions",
        "Dimensional Changes (SCD)"
    ])

    # =====================================================
    # 🔹 TAB 1
    # =====================================================
    with tab1:

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
        # 🔹 KEYS (FIXED CONNECTED ROOT + BETTER DEFINITIONS)
        # =====================================================
        st.subheader("Keys")

        center = st.columns([1,2,1])
        with center[1]:
            st.markdown("""
            <div style="
                text-align:center;
                padding:10px;
                border:2px solid #4CAF50;
                border-radius:8px;
                font-weight:bold;">
                KEYS
            </div>
            """, unsafe_allow_html=True)

        # 🔥 CONNECT ROOT TO LINE (FIX)
        st.markdown("""
        <div style="display:flex;justify-content:center;">
            <div style="width:2px;height:20px;background:#999;"></div>
        </div>
        """, unsafe_allow_html=True)

        # MAIN LINE
        st.markdown("""
        <div style="width:100%;height:2px;background:#999;margin-bottom:5px;"></div>
        """, unsafe_allow_html=True)

        # ARROWS
        arrow_cols = st.columns(7)
        for col in arrow_cols:
            with col:
                st.markdown("""
                <div style="text-align:center;">
                    <div style="width:2px;height:16px;background:#999;margin:auto;"></div>
                    <div style="width:0;height:0;
                        border-left:4px solid transparent;
                        border-right:4px solid transparent;
                        border-top:6px solid #999;
                        margin:auto;"></div>
                </div>
                """, unsafe_allow_html=True)

        # BOXES (DETAILED DEFINITIONS)
        k1,k2,k3,k4,k5,k6,k7 = st.columns(7)

        box = "padding:8px;border:2px solid #2196F3;border-radius:8px;font-size:12px;text-align:center;"

        k1.markdown(f"<div style='{box}'><b>Primary Key</b><br>Uniquely identifies each row</div>", unsafe_allow_html=True)
        k2.markdown(f"<div style='{box}'><b>Foreign Key</b><br>Connects fact & dimension tables</div>", unsafe_allow_html=True)
        k3.markdown(f"<div style='{box}'><b>Natural Key</b><br>Business identifier like email/id</div>", unsafe_allow_html=True)
        k4.markdown(f"<div style='{box}'><b>Surrogate Key</b><br>System-generated key (used in SCD)</div>", unsafe_allow_html=True)
        k5.markdown(f"<div style='{box}'><b>Composite Key</b><br>Combination of multiple columns</div>", unsafe_allow_html=True)
        k6.markdown(f"<div style='{box}'><b>Candidate Key</b><br>Possible primary keys</div>", unsafe_allow_html=True)
        k7.markdown(f"<div style='{box}'><b>Alternate Key</b><br>Unused candidate key</div>", unsafe_allow_html=True)

        # EXAMPLE
        st.markdown("### 📊 Example")

        c1,c2 = st.columns(2)

        c1.dataframe(pd.DataFrame([
            [1,"C101","john@email.com","Bangalore"],
            [2,"C102","mike@email.com","Chennai"]
        ],columns=["cust_key (PK)","cust_id (NK)","email","city"]),hide_index=True)

        c2.dataframe(pd.DataFrame([
            [1,500],
            [2,300]
        ],columns=["cust_key (FK)","sales_amt"]),hide_index=True)


        # =====================================================
        # 🔹 GRAIN + MEASURES (SIDE BY SIDE)
        # =====================================================
        left,right = st.columns(2)

        # ---------------- GRAIN ----------------
        with left:
            st.subheader("Grain")

            st.dataframe(pd.DataFrame([
                ["Definition","Defines what one row represents"],
                ["Purpose","Controls level of detail"],
                ["Impact","Affects aggregation accuracy"]
            ],columns=["Aspect","Explanation"]),hide_index=True)

            st.markdown("**Example**")

            st.dataframe(pd.DataFrame([
                ["1001","iPhone","800"],
                ["1002","Laptop","1200"]
            ],columns=["order_id","product","amount"]),hide_index=True)

            st.dataframe(pd.DataFrame([
                ["2024-01-01","5000"],
                ["2024-01-02","7000"]
            ],columns=["date","total_sales"]),hide_index=True)

            st.dataframe(pd.DataFrame([
                ["Wrong Grain","Incorrect results"],
                ["Too High","Loss of detail"],
                ["Too Low","Performance issues"]
            ],columns=["Scenario","Impact"]),hide_index=True)

        # ---------------- MEASURES ----------------
        with right:
            st.subheader("Measures")

            st.dataframe(pd.DataFrame([
                ["Definition","Numeric values in fact table"],
                ["Usage","Used in aggregations"]
            ],columns=["Aspect","Explanation"]),hide_index=True)

            st.markdown("### Types")

            m1,m2,m3 = st.columns(3)

            m1.markdown("<div style='border:2px solid #4CAF50;padding:8px;text-align:center'><b>Additive</b><br>Can sum across all dims<br>Ex: sales</div>", unsafe_allow_html=True)
            m2.markdown("<div style='border:2px solid #ff9800;padding:8px;text-align:center'><b>Semi</b><br>Limited aggregation<br>Ex: balance</div>", unsafe_allow_html=True)
            m3.markdown("<div style='border:2px solid #f44336;padding:8px;text-align:center'><b>Non</b><br>No aggregation<br>Ex: ratio</div>", unsafe_allow_html=True)


        render_ai_chat("dim_core","Ask about Core Concepts","Dimensional Modeling Core Concepts")


    # =====================================================
    # 🔹 TAB 2
    # =====================================================
    with tab2:

        col1, col2 = st.columns(2)

        # ---------------- STAR ----------------
        with col1:
            st.subheader("Star Schema")

            st.markdown("""
        <div style='text-align:center;font-size:12px'>

        <div style='padding:6px;border:2px solid #4CAF50;display:inline-block'>
        Date_dim
        </div>

        <div>↓</div>

        <div style='display:flex;justify-content:center;align-items:center;gap:6px'>

        <div style='padding:6px;border:2px solid #4CAF50'>
        Customer_dim
        </div>

        <div>→</div>

        <div style='padding:8px;border:2px solid #2196F3;background:#eef7ff'>
        <b>Sales_fact</b>
        </div>

        <div>←</div>

        <div style='padding:6px;border:2px solid #4CAF50'>
        Product_dim
        </div>

        </div>

        <div>↑</div>

        <div style='padding:6px;border:2px solid #4CAF50;display:inline-block'>
        Store_dim
        </div>

        </div>
        """, unsafe_allow_html=True)


        # ---------------- SNOWFLAKE ----------------
        with col2:
            st.subheader("Snowflake Schema")

            st.markdown("""
        <div style='text-align:center;font-size:12px'>

        <div style='padding:6px;border:2px solid #4CAF50;display:inline-block'>Category</div>
        <div>↓</div>
        <div style='padding:6px;border:2px solid #4CAF50;display:inline-block'>Product</div>
        <div>↓</div>

        <div style='display:flex;justify-content:center;align-items:center;gap:8px'>

        <div style='padding:6px;border:2px solid #4CAF50'>Date</div>

        <div>→</div>

        <div style='padding:8px;border:2px solid #2196F3;background:#eef7ff'>
        <b>Sales_fact</b>
        </div>

        <div>←</div>

        <div style='padding:6px;border:2px solid #4CAF50'>Store</div>

        </div>

        <div>↑</div>
        <div style='padding:6px;border:2px solid #4CAF50;display:inline-block'>Customer</div>
        <div>↑</div>
        <div style='padding:6px;border:2px solid #4CAF50;display:inline-block'>Region</div>

        </div>
        """, unsafe_allow_html=True)

        render_ai_chat("dim_schema","Ask about Schemas","Star & Snowflake")


    # =====================================================
    # 🔹 TAB 3
    # =====================================================
    with tab3:

        st.subheader("Dimension Types")

        # ROOT
        center = st.columns([1,2,1])
        with center[1]:
            st.markdown("""
            <div style='text-align:center;border:2px solid #4CAF50;padding:10px;font-weight:bold'>
            DIMENSION TYPES
            </div>
            """, unsafe_allow_html=True)

        # CONNECTOR
        st.markdown("""
        <div style='display:flex;justify-content:center'>
            <div style='width:2px;height:20px;background:#999'></div>
        </div>
        """, unsafe_allow_html=True)

        # MAIN LINE
        st.markdown("<div style='width:100%;height:2px;background:#999'></div>", unsafe_allow_html=True)

        # ARROWS
        arrow_cols = st.columns(7)
        for col in arrow_cols:
            col.markdown("""
            <div style="text-align:center;">
                <div style="width:2px;height:14px;background:#999;margin:auto;"></div>
                <div style="width:0;height:0;
                    border-left:4px solid transparent;
                    border-right:4px solid transparent;
                    border-top:6px solid #999;
                    margin:auto;"></div>
            </div>
            """, unsafe_allow_html=True)

        # BOXES WITH BETTER DEFINITIONS
        cols = st.columns(7)

        box = "border:2px solid #4CAF50;padding:8px;font-size:12px;text-align:center"

        cols[0].markdown(f"<div style='{box}'><b>Conformed</b><br>Shared across multiple fact tables ensuring consistent reporting</div>", unsafe_allow_html=True)
        cols[1].markdown(f"<div style='{box}'><b>Role Playing</b><br>Same dimension reused for different roles like order_date, ship_date</div>", unsafe_allow_html=True)
        cols[2].markdown(f"<div style='{box}'><b>Degenerate</b><br>Dimension key stored in fact table without separate dimension table</div>", unsafe_allow_html=True)
        cols[3].markdown(f"<div style='{box}'><b>Junk</b><br>Combines multiple low-cardinality flags into a single dimension</div>", unsafe_allow_html=True)
        cols[4].markdown(f"<div style='{box}'><b>Bridge</b><br>Handles many-to-many relationships between dimensions</div>", unsafe_allow_html=True)
        cols[5].markdown(f"<div style='{box}'><b>Hierarchical</b><br>Represents parent-child relationships like country → state → city</div>", unsafe_allow_html=True)
        cols[6].markdown(f"<div style='{box}'><b>Factless</b><br>Stores relationships/events without numeric measures</div>", unsafe_allow_html=True)

        # =====================================================
        # 🔥 SCD TYPE 2 (SIMULATOR + FIXED UI + IMPLEMENTATION)
        # =====================================================
        st.subheader("SCD Type 2 Simulator")

        cities = ["Chennai", "Bangalore", "Hyderabad", "Mumbai"]

        # =====================================================
        # 🔹 INIT STATE
        # =====================================================
        if "scd_adv" not in st.session_state:
            st.session_state.scd_adv = pd.DataFrame([
                [1, "John", "Chennai", "2020-01-01", None, "Y"]
            ], columns=["id", "name", "city", "start_date", "end_date", "current"])


        # =====================================================
        # 🔹 FORM (ALIGNMENT FIXED)
        # =====================================================
        with st.form("scd_form"):

            c1, c2 = st.columns([2,1])

            with c1:
                new_city = st.selectbox("New City", cities)

            with c2:
                st.markdown("<br>", unsafe_allow_html=True)
                apply = st.form_submit_button("Apply Movement")


        # =====================================================
        # 🔹 PROCESS LOGIC (UNCHANGED)
        # =====================================================
        before = st.session_state.scd_adv.copy()

        if apply:
            df = before.copy()

            # expire old record
            df.loc[df["current"] == "Y", "end_date"] = str(datetime.now().date())
            df.loc[df["current"] == "Y", "current"] = "N"

            # insert new record
            new_row = pd.DataFrame([
                [1, "John", new_city, str(datetime.now().date()), None, "Y"]
            ], columns=df.columns)

            df = pd.concat([df, new_row], ignore_index=True)

            st.session_state.scd_adv = df

        after = st.session_state.scd_adv


        # =====================================================
        # 🔹 SIDE-BY-SIDE VIEW
        # =====================================================
        c1, c2 = st.columns(2)

        with c1:
            st.markdown("### Before")
            st.dataframe(before, use_container_width=False, hide_index=True)

        with c2:
            st.markdown("### After")
            st.dataframe(after, use_container_width=False, hide_index=True)


        # =====================================================
        # 🔹 FLOW EXPLANATION
        # =====================================================
        st.markdown("""
        **Flow:**
        - Old Row → Expired (end_date updated, current = N)  
        - New Row → Inserted (current = Y)  
        - Full History → Preserved  
        """)


        # =====================================================
        # 🔥 IMPLEMENTATION (OPTIMIZED WITH TOGGLE)
        # =====================================================
        st.subheader("SCD Type 2 Implementation")

        mode = st.radio(
            "Choose Implementation",
            ["SQL", "PySpark"],
            horizontal=True
        )

        # ---------------- SQL ----------------
        if mode == "SQL":
            st.code("""
        -- STEP 1: Expire existing record
        UPDATE dim_customer
        SET end_date = CURRENT_DATE, current = 'N'
        WHERE customer_id = 1 AND current = 'Y';

        -- STEP 2: Insert new record
        INSERT INTO dim_customer (customer_id, name, city, start_date, end_date, current)
        VALUES (1, 'John', 'Bangalore', CURRENT_DATE, NULL, 'Y');
        """)

        # ---------------- PYSPARK ----------------
        else:
            st.code("""
        from pyspark.sql.functions import current_date, lit

        # STEP 1: Separate current and history
        current_df = df.filter("current = 'Y'")
        history_df = df.filter("current = 'N'")

        # STEP 2: Expire current records
        expired_df = current_df.withColumn("end_date", current_date()) \\
                            .withColumn("current", lit("N"))

        # STEP 3: Create new record
        new_data = [(1, "John", "Bangalore", None, None, "Y")]

        new_df = spark.createDataFrame(new_data, df.columns) \\
                    .withColumn("start_date", current_date())

        # STEP 4: Merge all data
        final_df = history_df.union(expired_df).union(new_df)
        """)

        # =====================================================
        # 🔥 KEY TAKEAWAY
        # =====================================================
        st.markdown("""
        ### 🔥 Key Flow

        - Existing active row → **expired (end_date updated)**
        - New row → **inserted with current = Y**
        - Old data → **preserved (history maintained)**

        👉 This is the core of **Slowly Changing Dimension Type 2**
        """)


        render_ai_chat("dim_scd","Ask about SCD","SCD Type 2")
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