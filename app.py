import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(layout="wide")

# --- simple auth guard
from core.auth import create_user, login_user
from core.db import SessionLocal

# --- persistent login using query params + session state
if "user" not in st.session_state:
    st.session_state["user"] = None

# Comprehensive Dark-mode CSS to override inline styles across all modules
st.markdown(
    """
    <style>
    [data-theme='dark'] .stApp { background-color: #0e1117; }

    /* Force visibility for all div elements with inline backgrounds in dark mode */
    [data-theme='dark'] [style*="background"], [data-theme='dark'] [style*="background-color"] {
        background-color: #1e293b !important;
        color: #f1f5f9 !important;
        border-color: #334155 !important;
    }

    /* Specifically target text inside those divs to be light */
    [data-theme='dark'] [style*="background"] *, [data-theme='dark'] [style*="background-color"] * {
        color: #f1f5f9 !important;
    }

    /* Target specific light hex codes used in modules for Datamodeling, Spark, and GenAI */
    [data-theme='dark'] [style*="#E8F4FD" i], [data-theme='dark'] [style*="#e8f4fd" i],
    [data-theme='dark'] [style*="#E9EEF4" i], [data-theme='dark'] [style*="#edf3ea" i],
    [data-theme='dark'] [style*="#f8f1e6" i], [data-theme='dark'] [style*="#f3f4f6" i],
    [data-theme='dark'] [style*="#f3eef6" i], [data-theme='dark'] [style*="#f8edee" i],
    [data-theme='dark'] [style*="#ecf3f2" i], [data-theme='dark'] [style*="#eff6ff" i],
    [data-theme='dark'] [style*="#f0fdfa" i], [data-theme='dark'] [style*="#fffbeb" i],
    [data-theme='dark'] [style*="#fef3c7" i], [data-theme='dark'] [style*="#f1f5f9" i],
    [data-theme='dark'] [style*="#dbeafe" i], [data-theme='dark'] [style*="#dcfce7" i],
    [data-theme='dark'] [style*="#eef7ff" i], [data-theme='dark'] [style*="#e6f4ea" i],
    [data-theme='dark'] [style*="#fff4e5" i], [data-theme='dark'] [style*="#fdecea" i],
    [data-theme='dark'] [style*="#ffffff" i], [data-theme='dark'] [style*="#fff" i], 
    [data-theme='dark'] [style*="background:white" i], [data-theme='dark'] [style*="background: white" i],
    [data-theme='dark'] [style*="#fafafa" i], [data-theme='dark'] [style*="#f8fafc" i],
    [data-theme='dark'] [style*="#F8FAFC" i], [data-theme='dark'] [style*="#e5e7eb" i],
    [data-theme='dark'] [style*="#EEF2FF" i], [data-theme='dark'] [style*="#FDECEA" i],
    [data-theme='dark'] [style*="#E6F4EA" i], [data-theme='dark'] [style*="#FFF4E5" i],
    [data-theme='dark'] [style*="#fee2e2" i], [data-theme='dark'] [style*="#fecaca" i],
    [data-theme='dark'] [style*="#bbf7d0" i], [data-theme='dark'] [style*="#fef3c7" i],
    [data-theme='dark'] [style*="#E9EEF4" i], [data-theme='dark'] [style*="#EDF3EA" i],
    [data-theme='dark'] [style*="#F8F1E6" i], [data-theme='dark'] [style*="#F3F4F6" i],
    [data-theme='dark'] [style*="#F3EEF6" i], [data-theme='dark'] [style*="#F8EDEE" i],
    [data-theme='dark'] [style*="#ECF3F2" i], [data-theme='dark'] [style*="#DCE5EF" i],
    [data-theme='dark'] [style*="#DEEAD8" i], [data-theme='dark'] [style*="#F1E4CF" i],
    [data-theme='dark'] [style*="#4CAF50" i], [data-theme='dark'] [style*="#2196F3" i], 
    [data-theme='dark'] [style*="#FF9800" i], [data-theme='dark'] [style*="#9C27B0" i] {
        background-color: #1e293b !important;
        color: #f8fafc !important;
    }

    [data-theme='dark'] [style*="#f8fafc" i],
    [data-theme='dark'] [style*="#fafafa" i],
    [data-theme='dark'] [style*="#e8f4fd" i],
    [data-theme='dark'] [style*="#e6f4ea" i],
    [data-theme='dark'] [style*="#fdecea" i], 
    [data-theme='dark'] [style*="color:#0f172a" i], [data-theme='dark'] [style*="color:#475569" i],
    [data-theme='dark'] [style*="#eef7ff" i] {
        background: #0b1220 !important;
        color: #e6eef8 !important;
    }

    [data-theme='dark'] .stMarkdown, [data-theme='dark'] .stMarkdown p, 
    [data-theme='dark'] .stMarkdown span, [data-theme='dark'] .stMarkdown b,
    [data-theme='dark'] .stMarkdown strong, [data-theme='dark'] .stMarkdown li {
        color: #e2e8f0 !important;
    }

    [data-theme='dark'] table, [data-theme='dark'] th, [data-theme='dark'] td {
        color: #f1f5f9 !important;
        border-color: #334155 !important;
    }

    [data-theme='dark'] pre, [data-theme='dark'] code, [data-theme='dark'] .stCodeBlock {
        background-color: #111827 !important;
        color: #e5e7eb !important;
    }

    [data-theme='dark'] .stDataFrame, [data-theme='dark'] .stTable {
        background-color: #0f172a !important;
    }

    [data-theme='dark'] header, [data-theme='dark'] [data-testid="stHeader"] {
        background-color: rgba(14, 17, 23, 0.8) !important;
    }

    /* Fix for project section client requirements */
    [data-theme='dark'] [style*="min-height:108px"] {
        background-color: #1e293b !important;
        border: 1px solid #475569 !important;
    }

    /* Filter for Ace Editor to prevent light theme glare in dark mode */
    [data-theme='dark'] .ace_editor {
        filter: invert(0.9) hue-rotate(180deg) !important;
    }
    [data-theme='dark'] input, [data-theme='dark'] textarea, [data-theme='dark'] select { color:#e6eef8 !important; background:#071233 !important; border-color:#334155 !important }
    [data-theme='dark'] .stAlert { color:#e6eef8 !important; background:#071233 !important; border-color:#334155 !important }
    </style>
    """,
    unsafe_allow_html=True,
)

# If client has stored user in localStorage, ensure URL contains it so Streamlit can restore on reload
components.html(
    """
    <script>
    (function(){
        try{
            const ONE_HOUR = 60*60*1000;
            const params = new URLSearchParams(window.location.search);
            const stored = localStorage.getItem('ai_data_user');
            const ts = parseInt(localStorage.getItem('ai_data_user_ts')||'0',10);
            const now = Date.now();

            // If the stored session is older than 1 hour, clear storage and remove user param
            if (stored && ts && (now - ts > ONE_HOUR)) {
                localStorage.removeItem('ai_data_user');
                localStorage.removeItem('ai_data_user_ts');
                sessionStorage.removeItem('ai_data_user_restored');
                if (params.has('user')) {
                    params.delete('user');
                    const newUrl = window.location.pathname + (params.toString() ? '?' + params.toString() : '');
                    window.location.replace(newUrl);
                    return;
                }
            }

            // If no user param but localStorage has a fresh user, restore once
            if (!params.has('user') && stored && (!sessionStorage.getItem('ai_data_user_restored'))) {
                sessionStorage.setItem('ai_data_user_restored','1');
                params.set('user', stored);
                window.location.replace(window.location.pathname + '?' + params.toString());
                return;
            }

            // Keep timestamp refreshed on user activity
            function touch(){ if(localStorage.getItem('ai_data_user')){ localStorage.setItem('ai_data_user_ts', Date.now().toString()); } }
            ['click','keydown','mousemove','touchstart'].forEach(evt=>window.addEventListener(evt, touch, {passive:true}));

            // Periodic inactivity check (1 minute)
            setInterval(function(){
                const stored2 = localStorage.getItem('ai_data_user');
                const ts2 = parseInt(localStorage.getItem('ai_data_user_ts')||'0',10);
                if(stored2 && ts2 && (Date.now() - ts2 > ONE_HOUR)){
                    localStorage.removeItem('ai_data_user');
                    localStorage.removeItem('ai_data_user_ts');
                    sessionStorage.removeItem('ai_data_user_restored');
                    const p = new URLSearchParams(window.location.search);
                    if(p.has('user')){ p.delete('user'); }
                    const newUrl = window.location.pathname + (p.toString() ? '?' + p.toString() : '');
                    window.location.replace(newUrl);
                }
            }, 60*1000);
        }catch(e){console.warn(e)}
    })();
    </script>
    """,
    height=0,
)
# If URL has ?user= set, try to restore session
def _set_auth_url(username):
    """Helper to strictly set user in URL and reload if necessary."""
    st.query_params["user"] = username
    # Extra JS insurance to ensure the URL bar reflects the change and localStorage is synced
    components.html(f"""
    <script>
    try{{
        localStorage.setItem('ai_data_user', '{username}');
        localStorage.setItem('ai_data_user_ts', Date.now().toString());
        const params = new URLSearchParams(window.location.search);
        if(params.get('user') !== '{username}'){{
            params.set('user', '{username}');
            window.location.replace(window.location.pathname + '?' + params.toString());
        }}
    }}catch(e){{console.warn(e)}}
    </script>
    """, height=0)

def _clear_auth_url():
    """Helper to strictly clear user from URL and localStorage."""
    st.query_params.pop("user", None)
    components.html("""
    <script>
    try{
        localStorage.removeItem('ai_data_user');
        localStorage.removeItem('ai_data_user_ts');
        sessionStorage.removeItem('ai_data_user_restored');
    }catch(e){console.warn(e)}
    </script>
    """, height=0)

def _safe_query_param(name):
    v = st.query_params.get(name)
    if v is None:
        return None
    # st.query_params may return a list or a string
    if isinstance(v, list):
        return v[0] if v else None
    # guard against empty string
    return v if v != "" else None

url_user = _safe_query_param("user")
if url_user and st.session_state["user"] is None:
    try:
        # validate user exists
        session = SessionLocal()
        from core.models import User
        u = session.query(User).filter_by(username=url_user).first()
        session.close()
        if u:
            st.session_state["user"] = u.username
        else:
            # Fallback: trust the query param if DB lookup is inconclusive
            st.session_state["user"] = url_user
    except Exception:
        # Ensure session doesn't break if DB is temporarily unreachable during refresh
        st.session_state["user"] = url_user

# --- Sidebar logic (Moved up so it's defined even during login check)
with st.sidebar:
    if st.session_state.get("user"):
        st.write(f"Logged in as: **{st.session_state['user']}**")
        if st.button("Logout"):
            st.session_state["user"] = None
            _clear_auth_url()
            if hasattr(st, "rerun"):
                st.rerun()
            else:
                st.experimental_rerun()


# --- Login UI
if not st.session_state.get("user"):
    st.title("Welcome to AI Data Engineering")
    
    with st.form("auth_form", clear_on_submit=False):
        st.subheader("Login or Signup")
        username = st.text_input("Username", key="auth_user")
        password = st.text_input("Password", type="password", key="auth_pass")
        
        col1, col2 = st.columns(2)
        login_clicked = col1.form_submit_button("Login", use_container_width=True)
        signup_clicked = col2.form_submit_button("Signup", use_container_width=True)

    if login_clicked:
        if not username.strip() or not password.strip():
            st.error("Username and password cannot be empty.")
        else:
            user = login_user(username, password)
            if user:
                st.session_state["user"] = user.username
                _set_auth_url(user.username)
                st.rerun()
            else:
                st.error("Invalid credentials")

    if signup_clicked:
        if not username.strip() or not password.strip():
            st.error("Username and password cannot be empty.")
        else:
            try:
                create_user(username, password)
                st.success("User created successfully! You can now log in.")
            except ValueError as ve:
                st.error(str(ve))
            except Exception:
                st.error("An error occurred during signup. The username might already be taken.")

    st.stop()

# ---------------- SECTION LABELS ----------------
DASHBOARD_SECTION_LABEL = "Dashboard"
CONCEPTS_SECTION_LABEL = "Concepts"
GENAI_SECTION_LABEL = "GenAI"
CODING_SECTION_LABEL = "Coding"
PYTHON_SECTION_LABEL = "Python"
SPARK_SECTION_LABEL = "Spark"
DATA_MODELING_SECTION_LABEL = "Data Modelling"
PROJECTS_SECTION_LABEL = "Projects"

SECTION_ORDER = [
    DASHBOARD_SECTION_LABEL,
    CONCEPTS_SECTION_LABEL,
    GENAI_SECTION_LABEL,
    CODING_SECTION_LABEL,
    SPARK_SECTION_LABEL,
    DATA_MODELING_SECTION_LABEL,
    PROJECTS_SECTION_LABEL,
]

# ---------------- URL PARAM HANDLING ----------------
query_params = st.query_params

# ✅ STEP 1: Initialize session FIRST (source of truth)
if "module" not in st.session_state:
    st.session_state["module"] = DASHBOARD_SECTION_LABEL

# ✅ STEP 2: If URL has module → override session
if "module" in query_params:
    st.session_state["module"] = query_params["module"]

# ✅ STEP 3: Use session as final value
selected_module = st.session_state["module"]

# ---------------- LEGACY MAP ----------------
legacy_module_map = {
    "SQL": CODING_SECTION_LABEL,
    "SQL + PySpark": CODING_SECTION_LABEL,
    "PySpark": SPARK_SECTION_LABEL,
    PYTHON_SECTION_LABEL: CODING_SECTION_LABEL,
}

selected_module = legacy_module_map.get(selected_module, selected_module)

if query_params.get("module") == PYTHON_SECTION_LABEL and "coding_track" not in st.query_params:
    st.query_params["coding_track"] = "Python"

if selected_module not in SECTION_ORDER:
    selected_module = DASHBOARD_SECTION_LABEL

# ---------------- SIDEBAR ----------------
module = st.sidebar.selectbox(
    "Choose Section",
    SECTION_ORDER,
    index=SECTION_ORDER.index(selected_module),
    label_visibility="collapsed",
)

# ✅ STEP 4: Sync BOTH (CRITICAL)
st.session_state["module"] = module
st.query_params["module"] = module


# =========================================================
# ---------------- ROUTING ----------------
# =========================================================

if module == CODING_SECTION_LABEL:
    from modules.coding.ui import render_coding
    render_coding()

elif module == CONCEPTS_SECTION_LABEL:
    from modules.concepts.ui import render_concepts
    render_concepts()

elif module == GENAI_SECTION_LABEL:
    from modules.genai.ui import render_genai
    render_genai()

elif module == SPARK_SECTION_LABEL:
    from modules.spark.ui import render_spark
    render_spark()

elif module == DATA_MODELING_SECTION_LABEL:
    from modules.datamodeling.ui import render_datamodeling
    render_datamodeling()

elif module == PROJECTS_SECTION_LABEL:
    from modules.projects.ui import render_projects
    render_projects()

elif module == DASHBOARD_SECTION_LABEL:
    import matplotlib.pyplot as plt
    from core.interview import load_interview_history
    from core.loader import load_questions
    from core.progress import load_progress

    st.title("📊 Dashboard")

    modules = [
        {"label": "SQL", "question_module": "sql", "progress_track": "sql"},
        {"label": "Spark", "question_module": "sql", "progress_track": "pyspark"},
        {"label": "Python", "question_module": "python", "progress_track": "python"},
    ]

    cols = st.columns(3)

    for i, module_config in enumerate(modules):
        with cols[i % 3]:
            try:
                questions = load_questions(module_config["question_module"])
            except Exception:
                questions = []

            total = len(questions)
            solved_keys = load_progress(module_config["progress_track"])
            solved = len([q for q in questions if q.get("progress_key") in solved_keys])
            unsolved = total - solved

            st.markdown(f"### 📘 {module_config['label'].upper()}")

            if total == 0:
                st.info("No questions yet")
                continue

            fig, ax = plt.subplots(figsize=(2.5, 2.5))
            ax.pie(
                [solved, unsolved],
                labels=["✔", "✖"],
                autopct="%1.0f%%",
                textprops={"fontsize": 8},
            )
            ax.axis("equal")

            st.pyplot(fig)

            st.markdown(
                f"""
                <div style="text-align:center;">
                    <b>{solved} / {total}</b><br>
                    <small>Solved</small>
                </div>
                """,
                unsafe_allow_html=True,
            )

            st.markdown(
                f"""
                <div style="text-align:center;">
                    <b>{solved} / {total}</b><br>
                    <small>Solved</small>
                </div>
                """,
                unsafe_allow_html=True
            )

    st.markdown("---")
    st.subheader("Interview Simulator")

    history = load_interview_history()

    if not history:
        st.info("No interview runs yet.")
    else:
        latest_run = history[-1]
        best_run = max(history, key=lambda run: run.get("score_percent", 0))
        average_score = round(
            sum(run.get("score_percent", 0) for run in history) / len(history),
            1,
        )

        metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)
        metric_col1.metric("Runs", len(history))
        metric_col2.metric("Latest Score", f"{latest_run['score_percent']}%")
        metric_col3.metric("Best Score", f"{best_run['score_percent']}%")
        metric_col4.metric("Average Score", f"{average_score}%")

        recent_runs = []
        for run in reversed(history[-5:]):
            recent_runs.append({
                "finished_at": run["finished_at"],
                "track": run["track"],
                "score": f"{run['total_score']} / {run['max_score']}",
                "accuracy": f"{run['correct_count']} / {run['total_questions']}",
                "time_used": f"{run.get('elapsed_seconds', 0)}s",
                "reason": run.get("finished_reason", "completed").replace("_", " ").title(),
            })

        st.dataframe(recent_runs, use_container_width=True, hide_index=True)
