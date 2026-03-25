import streamlit as st
import pandas as pd
from core.ai import ask_ai
import random

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

def generate_ai_questions(topic):
    domain = random.choice([
        "e-commerce", "banking", "ride-sharing",
        "streaming platforms", "healthcare"
    ])

    prompt = f"""
    You are a senior data engineer interviewer at Amazon, Google, or Microsoft.

    Generate 5 HIGH-QUALITY interview questions WITH ANSWERS on {topic}.

    Requirements:
    - Mix conceptual + scenario-based + system design questions
    - Use real-world systems ({domain})
    - Questions must feel like FAANG interviews
    - Avoid generic textbook questions
    - Each answer must be precise, structured, and practical
    - Include reasoning + small schema/example if needed

    Format STRICTLY:

    Q1: Question

    Answer:
    - Point 1
    - Point 2
    - Example (if needed)

    Ensure variety and no repetition.
    """

    return ask_ai(prompt)


# =========================================================
# 🔹 ENTRY POINT
# =========================================================

def render_datamodeling():
    render_title("📊 Data Modelling")

    tab1, tab2, tab3, tab4 = st.tabs([
        "Fundamentals",
        "Dimensional Modeling",
        "Architecture",
        "Distributed"
    ])

    with tab1:
        show_fundamentals()

    with tab2:
        st.info("Coming next...")

    with tab3:
        st.info("Coming next...")

    with tab4:
        st.info("Coming next...")


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

        if st.button("Generate Normalization Q&A", key="norm_q"):
            st.markdown(generate_ai_questions("Normalization"))

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

        if st.button("Generate OLTP/OLAP Q&A", key="olap_q"):
            st.markdown(generate_ai_questions("OLTP vs OLAP"))

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

        if st.button("Generate ER Q&A", key="er_q"):
            st.markdown(generate_ai_questions("ER Modeling"))

# =========================================================
# 2. DIMENSIONAL MODELING (your page 7.2)
# =========================================================
def show_dimensional_modeling():
    st.header("Dimensional Modeling")

    st.markdown("""
    - Fact Tables → metrics  
    - Dimension Tables → context  
    """)

    st.subheader("Example")

    st.code("""
    Sales_Fact(
        date_id,
        product_id,
        customer_id,
        sales_qty,
        sales_amt
    )
    """)

    st.code("""
    Product_Dim(product_id, name, category)
    Customer_Dim(customer_id, name, city)
    """)

    st.subheader("Grain")

    st.markdown("""
    - Transaction level  
    - Daily level  
    - Monthly level  
    """)

    st.subheader("Fact Types")

    fact_type = st.selectbox("Choose", [
        "Event Fact",
        "Factless Fact"
    ])

    if fact_type == "Event Fact":
        st.write("Tracks events like login, clicks")

    elif fact_type == "Factless Fact":
        st.write("No measures, only relationships")


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