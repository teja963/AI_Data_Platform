import streamlit as st
import time
from datetime import datetime, timedelta
from sqlalchemy.exc import SQLAlchemyError

# -------- SESSION INIT (MANDATORY) --------
if "user" not in st.session_state:
    st.session_state["user"] = None

if "role" not in st.session_state:
    st.session_state["role"] = "user"

if "signup_mode" not in st.session_state:
    st.session_state["signup_mode"] = False

if "pending_admin" not in st.session_state:
    st.session_state["pending_admin"] = None


from core.constants import (
    DASHBOARD_SECTION_LABEL,
    CONCEPTS_SECTION_LABEL,
    GENAI_SECTION_LABEL,
    CODING_SECTION_LABEL,
    PYTHON_SECTION_LABEL,
    SPARK_SECTION_LABEL,
    DATA_MODELING_SECTION_LABEL,
    ARCHITECTURE_SECTION_LABEL,
    PROJECTS_SECTION_LABEL,
    ADMIN_SECTION_LABEL,
    SECTION_ORDER,
)

st.set_page_config(layout="wide")

# --- Global Query Params Initialization (Fixes NameError) ---
query_params = st.query_params

# --- simple auth guard
from core.auth import create_user, login_user, verify_otp, generate_and_store_otp, update_password, verify_email_otp, validate_email, validate_phone
from core.activity import flush_section_activity, track_section_activity, track_section_render
from core.access import get_allowed_sections
from core.db import SessionLocal, get_database_host
from core.login_history import record_login
from core.models import User
from core.runtime import clear_cached_runtime_data, ensure_fresh_runtime, get_deploy_health


APP_VERSION = ensure_fresh_runtime()
SESSION_TTL_HOURS = 24


def _show_database_unavailable(error):
    database_host = get_database_host()
    st.error(
        "Database is currently unavailable. Please check the PostgreSQL/Neon connection URL "
        "in Streamlit secrets and try again."
    )
    if database_host:
        st.caption(f"Configured DB host: `{database_host}`")
    st.caption(f"Database detail: {error}")

# --- persistent login using query params + session state
if "user" not in st.session_state:
    st.session_state["user"] = None
if "role" not in st.session_state:
    st.session_state["role"] = "user"

# Comprehensive Dark-mode CSS to override inline styles across all modules
st.markdown(
    """
    <style>
    [data-theme='dark'] .stApp { background-color: #0e1117; }

    /* Theme-Aware Container Defaults (Light Mode) */
    .genai-box, .roadmap-card, .dm-box, .project-card, .coding-io-box, .spark-disk-box {
        background: #ffffff;
        border: 1px solid #cbd5e1;
        color: #0f172a;
    }
    .genai-box.active-blue { background: #eff6ff; border-color: #2563eb; border-width: 2px; }
    .genai-box.active-green { background: #f0fdfa; border-color: #0f766e; border-width: 2px; }
    .genai-box.active-amber { background: #fffbeb; border-color: #b45309; border-width: 2px; }
    .project-card.project-focus { background: #eff6ff; border-color: #2563eb; }
    .project-card.project-failure { background: #fef2f2; border-color: #dc2626; }
    /* Spark Specific status styles */
    .spark-mem-error { background: #fee2e2 !important; border-color: #f87171 !important; }
    .spark-disk-spill { background: #dcfce7 !important; color: #166534 !important; border-color: #4ade80 !important; }
    .spark-disk-error { background: #fee2e2 !important; color: #991b1b !important; border-color: #f87171 !important; }
    .spark-chip-active { background: #2563eb; color: white !important; }
    .spark-chip-idle { background: #e5e7eb; color: #0f172a !important; }
    .text-success { color: #10b981 !important; }
    .text-error { color: #ef4444 !important; }

    /* Dark Mode FORCE Overrides */
    [data-theme='dark'] .genai-box, 
    [data-theme='dark'] .roadmap-card,
    [data-theme='dark'] .dm-box,
    [data-theme='dark'] .project-card,
    [data-theme='dark'] .coding-io-box,
    [data-theme='dark'] .spark-disk-box,
    [data-theme='dark'] [style*="background"] {
        background: #1e293b !important;
        border-color: #334155 !important;
        color: #f1f5f9 !important;
    }

    /* Ensure all text inside themed boxes turns light in dark mode */
    [data-theme='dark'] .genai-box *, 
    [data-theme='dark'] .roadmap-card *,
    [data-theme='dark'] .dm-box *,
    [data-theme='dark'] .project-card *,
    [data-theme='dark'] .coding-io-box *,
    [data-theme='dark'] [style*="background"] *,
    [data-theme='dark'] [style*="color:#475569" i],
    [data-theme='dark'] [style*="color:#0f172a" i] {
        color: #f1f5f9 !important;
    }

    /* Dark Mode Specific Active Borders */
    [data-theme='dark'] .genai-box.active-blue { border-color: #3b82f6 !important; }
    [data-theme='dark'] .genai-box.active-green { border-color: #10b981 !important; }
    [data-theme='dark'] .genai-box.active-amber { border-color: #f59e0b !important; }
    [data-theme='dark'] .project-card.project-focus { border-color: #3b82f6 !important; }
    [data-theme='dark'] .project-card.project-failure { border-color: #ef4444 !important; }

    /* Dark Mode specific status colors for Spark */
    [data-theme='dark'] .spark-mem-error { background: #7f1d1d !important; color: #fecaca !important; border-color: #b91c1c !important; }
    [data-theme='dark'] .spark-disk-spill { background: #064e3b !important; color: #bbf7d0 !important; border-color: #059669 !important; }
    [data-theme='dark'] .spark-disk-error { background: #7f1d1d !important; color: #fecaca !important; border-color: #b91c1c !important; }
    [data-theme='dark'] .spark-chip-active { background: #3b82f6; color: white !important; }
    [data-theme='dark'] .spark-chip-idle { background: #334155; color: #cbd5e1 !important; }
    [data-theme='dark'] .text-success { color: #34d399 !important; }
    [data-theme='dark'] .text-error { color: #f87171 !important; }

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

    [data-theme='dark'] input, [data-theme='dark'] textarea, [data-theme='dark'] select { color:#e6eef8 !important; background:#071233 !important; border-color:#334155 !important }
    [data-theme='dark'] .stAlert { color:#e6eef8 !important; background:#071233 !important; border-color:#334155 !important }
    </style>
    """,
    unsafe_allow_html=True,
)

# If URL has ?user= set, try to restore session
def _set_auth_url(username):
    """Helper to strictly set user in URL and reload if necessary."""
    st.query_params["user"] = username
    st.query_params["auth_ts"] = str(int(time.time()))


def _clear_auth_url():
    """Helper to strictly clear user from URL."""
    st.query_params.pop("user", None)
    st.query_params.pop("auth_ts", None)


def _expire_session_if_needed():
    login_ts = st.session_state.get("login_ts")
    if not login_ts:
        return

    if datetime.utcnow() - login_ts > timedelta(hours=SESSION_TTL_HOURS):
        flush_section_activity(st.session_state.get("user"))
        st.session_state["user"] = None
        st.session_state["role"] = "user"
        st.session_state.pop("login_ts", None)
        _clear_auth_url()
        st.warning("Session expired after 24 hours. Please log in again.")
        st.rerun()

def _safe_query_param(name):
    v = st.query_params.get(name)
    if v is None:
        return None
    # st.query_params may return a list or a string
    if isinstance(v, list):
        return v[0] if v else None
    # guard against empty string
    if v == "":
        return None
    if name == "user" and "," in str(v):
        return str(v).split(",")[-1].strip()
    return v


def _set_query_param_if_changed(name, value):
    current_value = _safe_query_param(name)
    if current_value != value:
        st.query_params[name] = value


def _select_navigation_section():
    selected = st.session_state.get("nav_jump")
    if selected:
        st.session_state["module"] = selected
        _set_query_param_if_changed("module", selected)


def _render_section_navigation(visible_sections, selected_module):
    st.sidebar.markdown("### Navigation")
    st.sidebar.markdown(
        """
        <style>
        [data-testid="stSidebar"] [data-baseweb="select"] > div {
            border: 1px solid #2563eb;
            background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%);
            border-radius: 10px;
        }
        [data-theme='dark'] [data-testid="stSidebar"] [data-baseweb="select"] > div {
            background: linear-gradient(135deg, #1e3a8a 0%, #172554 100%);
            border-color: #60a5fa;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    if st.session_state.get("nav_jump") not in visible_sections:
        st.session_state["nav_jump"] = selected_module if selected_module in visible_sections else visible_sections[0]

    st.sidebar.selectbox(
        "Jump To Section",
        visible_sections,
        index=visible_sections.index(st.session_state["nav_jump"]),
        key="nav_jump",
        on_change=_select_navigation_section,
    )


def _show_deploy_status_banner():
    health = get_deploy_health()
    running_commit = health.get("running_commit") or ""
    latest_commit = health.get("latest_commit") or ""

    if running_commit and latest_commit and not health.get("is_current"):
        message = (
            "New GitHub version detected, but Streamlit Cloud is still running an older build. "
            f"Running: `{running_commit[:12]}` | GitHub latest: `{latest_commit[:12]}`. "
            "Refresh Latest App/Data clears cached data only; Streamlit Cloud must redeploy to load new Python source code."
        )
        st.error(message)

        notify_key = f"deploy_stale_notified::{latest_commit[:12]}"
        if not st.session_state.get(notify_key):
            st.toast("New GitHub version detected, but Streamlit has not redeployed yet.")
            st.session_state[notify_key] = True
    elif not latest_commit:
        st.warning(
            "Could not verify the latest GitHub commit from this running app. "
            "If updates are not appearing, check Streamlit Cloud GitHub connection and branch settings."
        )

# --- RESTORE SESSION FROM URL (Refresh Persistence) ---
# Pick up the 'user' parameter set by the JavaScript restoration script
url_user = _safe_query_param("user")
if url_user and not st.session_state.get("user"):
    auth_ts = _safe_query_param("auth_ts")
    if auth_ts:
        try:
            auth_age_seconds = time.time() - int(auth_ts)
        except (TypeError, ValueError):
            auth_age_seconds = SESSION_TTL_HOURS * 3600 + 1
        if auth_age_seconds > SESSION_TTL_HOURS * 3600:
            _clear_auth_url()
            st.warning("Session expired after 24 hours. Please log in again.")
            st.stop()
    try:
        session = SessionLocal()
        # Verify the user actually exists in the DB before restoring
        u = session.query(User).filter_by(username=url_user).first()
        if u:
            st.session_state["user"] = u.username
            st.session_state["role"] = u.role
            st.session_state.setdefault("login_ts", datetime.utcnow())
        session.close()
    except Exception:
        # DB connection might fail temporarily; don't set user if so
        pass


# --- Authentication Flow ---
# ----------1. SIGNUP ----------------
if st.session_state.get("signup_mode"):

    st.title("🚀 Create Account")

    step = st.session_state.get("step", 1)

    # ---- Progress Indicator ----
    progress = (step - 1) / 2
    st.progress(progress)

    st.caption(f"Step {step} of 3")

    st.divider()

    # ---------------- STEP 1 ----------------
    if step == 1:
        st.subheader("📧 Verify Email")

        email = st.text_input("Email Address")

        col1, col2 = st.columns(2)

        with col1:
            if st.button("Send OTP", width="stretch"):
                if validate_email(email):
                    generate_and_store_otp(email)
                    st.session_state["email"] = email
                    st.session_state["step"] = 2
                    st.success("OTP sent to your email")
                    st.rerun()
                else:
                    st.error("Invalid email")

        with col2:
            if st.button("⬅ Back", width="stretch"):
                st.session_state["signup_mode"] = False
                st.rerun()

    # ---------------- STEP 2 ----------------
    elif step == 2:
        st.subheader("🔐 Enter OTP")

        otp = st.text_input("Enter OTP")

        col1, col2 = st.columns(2)

        with col1:
            if st.button("Verify OTP", width="stretch"):
                if verify_email_otp(st.session_state["email"], otp):
                    st.session_state["step"] = 3
                    st.success("Email verified")
                    st.rerun()
                else:
                    st.error("Invalid or expired OTP")

        with col2:
            if st.button("⬅ Back", width="stretch"):
                st.session_state["step"] = 1
                st.rerun()

        st.info("Didn't receive OTP?")
        if st.button("🔄 Resend OTP"):
            generate_and_store_otp(st.session_state["email"])
            st.success("OTP resent")

    # ---------------- STEP 3 ----------------
    elif step == 3:
        st.subheader("👤 Account Details")

        name = st.text_input("Full Name")
        username = st.text_input("Username")
        phone = st.text_input("Phone")
        password = st.text_input("Password", type="password")

        col1, col2 = st.columns(2)

        with col1:
            if col1.button("Create Account", width="stretch"):
                if not all([name, username, password]):
                    st.warning("Please fill all required fields")
                else:
                    try:
                        create_user(
                            username,
                            password,
                            name,
                            st.session_state["email"],
                            phone
                        )

                        # ✅ FIX: show success + hold screen
                        st.session_state["signup_success"] = True
                        st.session_state["signup_mode"] = False
                        st.rerun()

                    except Exception as e:
                        st.error(str(e))

        with col2:
            if st.button("⬅ Back", width="stretch"):
                st.session_state["step"] = 2
                st.rerun()

    st.divider()

    # Exit option
    if st.button("❌ Cancel Signup"):
        st.session_state.clear()
        st.rerun()

    st.stop()

# ---------------- LOGIN FLOW ----------------
elif not st.session_state.get("user") and not st.session_state.get("pending_admin"):

    if st.session_state.get("signup_success"):
        st.success("✅ Account created successfully!")
        st.info("⏳ Wait for admin approval before login.")
        del st.session_state["signup_success"]
        
    st.title("Welcome to AI Data Engineering")

    with st.form("auth_form", clear_on_submit=False):
        st.subheader("Login")

        username = st.text_input("Username", key="auth_user").strip()
        password = st.text_input("Password", type="password", key="auth_pass").strip()

        col1, col2 = st.columns(2)
        login_clicked = col1.form_submit_button("Login", width="stretch")
        signup_clicked = col2.form_submit_button("Signup", width="stretch")

    if st.button("Forgot Password?"):
        st.session_state["forgot_password"] = True
        st.session_state["fp_step"] = 1
        st.rerun()

    if login_clicked and username and password:
        try:
            user = login_user(username, password)

            if user:
                if user.role == "admin":
                    st.session_state["pending_admin"] = user.username
                    st.rerun()
                else:
                    st.session_state["role"] = user.role
                    st.session_state["user"] = user.username
                    st.session_state["login_ts"] = datetime.utcnow()
                    _set_auth_url(user.username)
                    st.rerun()
            else:
                st.error("Invalid credentials")

        except PermissionError as pe:
            st.warning(str(pe))
        except SQLAlchemyError as db_error:
            _show_database_unavailable(db_error)

    if signup_clicked:
        st.session_state["signup_mode"] = True
        st.session_state["step"] = 1   # 🔥 IMPORTANT
        st.rerun()

    st.stop()

# If an admin user has successfully entered credentials and is pending 2FA, show the OTP form.
if st.session_state.get("pending_admin"):
    st.title("Two-Factor Authentication")
    with st.form("otp_form"):
        st.info(f"Admin Verification for **{st.session_state['pending_admin']}**")
        otp_code = st.text_input("Enter 6-digit Authenticator Code", max_chars=6)
        verify_clicked = st.form_submit_button("Verify & Login", width="stretch")
        
        if st.form_submit_button("Cancel"):
            st.session_state.pop("pending_admin")
            st.rerun()

    if verify_clicked:
        try:
            if verify_otp(st.session_state["pending_admin"], otp_code):
                session = SessionLocal()
                try:
                    u = session.query(User).filter_by(username=st.session_state["pending_admin"]).first()
                    st.session_state["user"] = u.username
                    st.session_state["role"] = u.role
                    st.session_state["login_ts"] = datetime.utcnow()
                    st.session_state.pop("pending_admin")
                    _set_auth_url(u.username)
                    record_login(u.id, u.username)
                finally:
                    session.close()
                st.rerun()
            else:
                st.error("Invalid Authenticator code.")
        except SQLAlchemyError as db_error:
            _show_database_unavailable(db_error)

    st.stop()

# --- Main Application Logic (Only reached if st.session_state["user"] is set) ---
if st.session_state.get("user"):
    _expire_session_if_needed()
    _show_deploy_status_banner()
    # --- Main App (Only reached if authenticated)
    with st.sidebar:
        st.write(f"User: **{st.session_state['user']}** ({st.session_state.get('role')})")
        st.caption(f"App version: `{APP_VERSION}`")
        if st.button("Refresh Latest App/Data", width="stretch"):
            clear_cached_runtime_data()
            st.success("Cleared cached data. Reloading latest available app state.")
            st.rerun()
        if st.button("Logout"):
            flush_section_activity(st.session_state.get("user"))
            st.session_state["user"] = None
            st.session_state["role"] = "user"
            _clear_auth_url()
            if hasattr(st, "rerun"):
                st.rerun()
            else:
                st.experimental_rerun()

    if "module" not in st.session_state:
        st.session_state["module"] = DASHBOARD_SECTION_LABEL

    # ✅ STEP 2: If URL has module → override session
    if "module" in query_params:
        st.session_state["module"] = query_params["module"]

    # ✅ STEP 3: Use session as final value
    selected_module = st.session_state["module"]

    legacy_module_map = {
        "SQL": CODING_SECTION_LABEL,
        "PySpark": SPARK_SECTION_LABEL,
        PYTHON_SECTION_LABEL: CODING_SECTION_LABEL,
    }

    selected_module = legacy_module_map.get(selected_module, selected_module)

    if query_params.get("module") == PYTHON_SECTION_LABEL and "coding_track" not in st.query_params:
        st.query_params["coding_track"] = "Python"

    if selected_module not in SECTION_ORDER:
        selected_module = DASHBOARD_SECTION_LABEL

    is_admin = st.session_state.get("role") == "admin"
    visible_sections = get_allowed_sections(st.session_state.get("user"), st.session_state.get("role", "user"))

    if selected_module not in visible_sections:
        selected_module = DASHBOARD_SECTION_LABEL
        st.session_state["module"] = selected_module

    _render_section_navigation(visible_sections, selected_module)
    module = st.session_state.get("module", selected_module)

    st.session_state["module"] = module
    _set_query_param_if_changed("module", module)
    track_section_activity(st.session_state.get("user"), module)

    def render_dashboard():
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
        chart_rows = []
        for i, module_config in enumerate(modules):
            with cols[i % 3]:
                try:
                    questions = load_questions(module_config["question_module"])
                except Exception:
                    questions = []

                total = len(questions)
                solved_keys = load_progress(module_config["progress_track"])
                solved = len([q for q in questions if q.get("progress_key") in solved_keys])
                st.markdown(f"### 📘 {module_config['label'].upper()}")

                if total == 0:
                    st.info("No questions yet")
                    continue

                progress_ratio = solved / total if total else 0
                st.metric("Solved", f"{solved} / {total}")
                st.progress(progress_ratio)
                st.caption(f"{round(progress_ratio * 100)}% complete")
                chart_rows.append({
                    "Track": module_config["label"],
                    "Solved": solved,
                    "Remaining": max(total - solved, 0),
                })

        if chart_rows:
            st.markdown("### Progress Overview")
            st.bar_chart(chart_rows, x="Track", y=["Solved", "Remaining"], stack=True)

        st.markdown("---")
        st.subheader("Interview Simulator")
        history = load_interview_history()
        if not history:
            st.info("No interview runs yet.")
        else:
            latest_run = history[-1]
            best_run = max(history, key=lambda run: run.get("score_percent", 0))
            average_score = round(sum(run.get("score_percent", 0) for run in history) / len(history), 1)
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Runs", len(history))
            m2.metric("Latest Score", f"{latest_run['score_percent']}%")
            m3.metric("Best Score", f"{best_run['score_percent']}%")
            m4.metric("Average Score", f"{average_score}%")
            recent_runs = [{"finished_at": r["finished_at"], "track": r["track"], "score": f"{r['total_score']}/{r['max_score']}", "accuracy": f"{r['correct_count']}/{r['total_questions']}", "time_used": f"{r.get('elapsed_seconds', 0)}s", "reason": r.get("finished_reason", "completed").replace("_", " ").title()} for r in reversed(history[-5:])]
            st.dataframe(recent_runs, width="stretch", hide_index=True)

    # Map labels to rendering functions
    ROUTER = {
        DASHBOARD_SECTION_LABEL: render_dashboard,
        CODING_SECTION_LABEL: lambda: __import__("modules.coding.ui", fromlist=["render_coding"]).render_coding(),
        CONCEPTS_SECTION_LABEL: lambda: __import__("modules.concepts.ui", fromlist=["render_concepts"]).render_concepts(),
        GENAI_SECTION_LABEL: lambda: __import__("modules.genai.ui", fromlist=["render_genai"]).render_genai(),
        SPARK_SECTION_LABEL: lambda: __import__("modules.spark.ui", fromlist=["render_spark"]).render_spark(),
        DATA_MODELING_SECTION_LABEL: lambda: __import__("modules.datamodeling.ui", fromlist=["render_datamodeling"]).render_datamodeling(),
        ARCHITECTURE_SECTION_LABEL: lambda: __import__("modules.architecture.ui", fromlist=["render_architecture"]).render_architecture(),
        PROJECTS_SECTION_LABEL: lambda: __import__("modules.projects.ui", fromlist=["render_projects"]).render_projects(),
        ADMIN_SECTION_LABEL: lambda: __import__("modules.admin.ui", fromlist=["render_admin"]).render_admin(),
    }

    if module in ROUTER:
        render_started_at = time.perf_counter()
        ROUTER[module]()
        render_elapsed_ms = int((time.perf_counter() - render_started_at) * 1000)
        track_section_render(st.session_state.get("user"), module, render_elapsed_ms)
        st.caption(f"Section loaded in {render_elapsed_ms} ms")
