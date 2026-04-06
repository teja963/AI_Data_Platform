import streamlit as st
import streamlit.components.v1 as components
import matplotlib.pyplot as plt
from core.constants import (
    DASHBOARD_SECTION_LABEL,
    CONCEPTS_SECTION_LABEL,
    GENAI_SECTION_LABEL,
    CODING_SECTION_LABEL,
    PYTHON_SECTION_LABEL,
    SPARK_SECTION_LABEL,
    DATA_MODELING_SECTION_LABEL,
    PROJECTS_SECTION_LABEL,
    ADMIN_SECTION_LABEL,
    SECTION_ORDER,
)

# Enforce non-interactive backend for reliable chart rendering
import matplotlib
matplotlib.use('Agg')

st.set_page_config(layout="wide")

# --- Global Query Params Initialization ---
query_params = st.query_params

# --- simple auth guard
from core.auth import create_user, login_user, verify_otp, generate_and_store_otp, update_password, verify_email_otp, validate_email, validate_phone
from core.db import SessionLocal
from core.models import User

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

# --- SESSION PERSISTENCE (Option 2: Stay logged in for 1 hour) ---
components.html(
    """
    <script>
    (function(){
        try{
            const ONE_HOUR = 3600000; 
            const params = new URLSearchParams(window.location.search);
            const stored = localStorage.getItem('ai_data_user');
            const ts = parseInt(localStorage.getItem('ai_data_user_ts')||'0',10);
            const now = Date.now();

            // Auto-logout if session expired
            if (stored && ts && (now - ts > ONE_HOUR)) {
                localStorage.removeItem('ai_data_user');
                localStorage.removeItem('ai_data_user_ts');
                if (params.has('user')) {
                    params.delete('user');
                    window.location.replace(window.location.pathname + '?' + params.toString());
                }
                return;
            }

            // Restore session if URL is empty but localStorage is fresh
            const urlUser = params.get('user');
            if ((!urlUser || urlUser === "") && stored) {
                params.set('user', stored);
                window.location.replace(window.location.pathname + '?' + params.toString());
            }

            // Update activity timestamp
            function touch(){ if(localStorage.getItem('ai_data_user')){ localStorage.setItem('ai_data_user_ts', Date.now().toString()); } }
            ['click','keydown','mousemove','touchstart'].forEach(evt=>window.addEventListener(evt, touch, {passive:true}));

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
    # Immediate JS sync to localStorage so refresh works right after login
    components.html(f"""
    <script>
    try{{
        localStorage.setItem('ai_data_user', '{username}');
        localStorage.setItem('ai_data_user_ts', Date.now().toString());
    }}catch(e){{}}
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

# --- RESTORE SESSION FROM URL ---
url_user = _safe_query_param("user")
if url_user and not st.session_state.get("user"):
    try:
        session = SessionLocal()
        u = session.query(User).filter_by(username=url_user).first()
        if u:
            st.session_state["user"] = u.username
            st.session_state["role"] = u.role
        session.close()
    except Exception:
        # Silence DB errors during restoration to prevent login loops
        pass


# --- Authentication Flow ---
# If no user is logged in and no admin is pending 2FA, show the login form.
# --- Authentication Flow (Strict Gating) ---
if st.session_state.get("signup_mode"):
    st.title("Register New Account")
    
    # Step management
    if "signup_step" not in st.session_state:
        st.session_state["signup_step"] = "email"

    if st.session_state["signup_step"] == "email":
        with st.form("email_verify_form"):
            u_email = st.text_input("Enter Email for Verification")
            if st.form_submit_button("Send OTP"):
                if validate_email(u_email):
                    # Check if email is already in use
                    session = SessionLocal()
                    exists = session.query(User).filter(User.email.ilike(u_email)).first()
                    session.close()
                    if exists:
                        st.error("This email is already registered.")
                    else:
                        otp = generate_and_store_otp(u_email)
                        st.session_state["temp_email"] = u_email
                        st.session_state["signup_step"] = "otp"
                        st.toast(f"OTP sent to {u_email}")
                        st.rerun()
                else:
                    st.error("Please enter a valid email.")

    elif st.session_state["signup_step"] == "otp":
        with st.form("otp_verify_form"):
            st.info(f"Verifying {st.session_state['temp_reg_data']['email']}")
            v_code = st.text_input("Enter 6-Digit Code")
            if st.form_submit_button("Verify Email"):
                if v_code == st.session_state.get("signup_otp"):
                    try:
                        data = st.session_state["temp_reg_data"]
                        create_user(
                            username=data["username"], password=data["password"],
                            full_name=data["full_name"], email=data["email"], phone=data["phone"]
                        )
                        # Mark verified in DB immediately after creation
                        session = SessionLocal()
                        u = session.query(User).filter_by(username=data["username"]).first()
                        if u: u.email_verified = True
                        session.commit()
                        session.close()
                        
                        st.success("Account created! Log in once admin approves you.")
                        st.session_state["signup_mode"] = False
                        st.session_state.pop("signup_step")
                        st.rerun()
                    except Exception as e:
                        st.error(str(e))
                else:
                    st.error("Invalid OTP code.")

    elif st.session_state["signup_step"] == "details":
        st.success(f"Email Verified: {st.session_state['temp_email']} ✅")
        with st.form("signup_details_dedicated"):
            f_name = st.text_input("Full Name")
            u_name = st.text_input("Username (min 3 chars)").strip().lower()
            u_phone = st.text_input("Phone Number (10 digits for India +91)")
            u_pass = st.text_input("Password (min 6 chars)", type="password")
            
            if st.form_submit_button("Complete Registration"):
                try:
                    create_user(
                        username=u_name, 
                        password=u_pass, 
                        full_name=f_name, 
                        email=st.session_state["temp_email"], 
                        phone=u_phone
                    )
                    # Auto-set verified as they just passed step 2
                    session = SessionLocal()
                    user_obj = session.query(User).filter_by(username=u_name).first()
                    if user_obj:
                        user_obj.email_verified = True
                        session.commit()
                    session.close()
                    
                    st.success("Account created! Log in once admin approves you.")
                    st.session_state["signup_mode"] = False
                    st.session_state.pop("signup_step")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))

    if st.button("Back to Login", key="back_to_login_signup"):
        st.session_state["signup_mode"] = False
        st.session_state.pop("signup_step", None)
        st.rerun()
    st.stop()

elif st.session_state.get("verify_mode"):
    st.title("Verify Your Email")
    with st.form("verification_form"):
        st.info(f"A code was sent to the email provided for **{st.session_state['verify_user']}**")
        v_code = st.text_input("Enter 6-Digit Code")
        if st.form_submit_button("Verify Email"):
            if verify_email_otp(st.session_state["verify_user"], v_code):
                st.success("Email verified! Your account is now pending admin approval.")
                st.session_state.pop("verify_mode")
                st.session_state.pop("signup_mode")
                st.session_state.pop("verify_user")
                st.rerun()
            else:
                st.error("Invalid code.")
    if st.button("Resend Code"):
        generate_and_store_otp(st.session_state["verify_user"])
        st.toast("New code sent!")
    if st.button("Back to Login", key="back_to_login_verify_page"):
        st.session_state.pop("verify_mode", None)
        st.rerun()
    st.stop()

elif st.session_state.get("forgot_password"):
    st.title("Reset Password")
    user_id = st.text_input("Enter Username or Email")
    if st.button("Send Reset OTP"):
        otp = generate_and_store_otp(user_id)
        if otp:
            st.session_state["reset_user"] = user_id
            st.success(f"OTP sent! (Dev hint: {otp})")
        else:
            st.error("User not found.")
    
    if st.session_state.get("reset_user"):
        with st.form("reset_form"):
            code = st.text_input("OTP Code")
            new_p = st.text_input("New Password", type="password")
            if st.form_submit_button("Update Password"):
                try:
                    update_password(st.session_state["reset_user"], new_p, code)
                    st.success("Password updated! You can now login.")
                    st.session_state.pop("forgot_password")
                    st.session_state.pop("reset_user")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))

    if st.button("Back"):
        st.session_state.pop("forgot_password")
        st.rerun()
    st.stop()

elif st.session_state.get("pending_admin"):
    st.title("Two-Factor Authentication")
    with st.form("otp_form"):
        st.info(f"Admin Verification for **{st.session_state['pending_admin']}**")
        otp_code = st.text_input("Enter 6-digit Authenticator Code", max_chars=6)
        verify_clicked = st.form_submit_button("Verify & Login", use_container_width=True)
        
        if st.form_submit_button("Cancel"):
            st.session_state.pop("pending_admin")
            st.rerun()

    if verify_clicked:
        if verify_otp(st.session_state["pending_admin"], otp_code):
            session = SessionLocal()
            u = session.query(User).filter_by(username=st.session_state["pending_admin"]).first()
            st.session_state["user"] = u.username
            st.session_state["role"] = u.role
            st.session_state.pop("pending_admin")
            _set_auth_url(u.username)
            session.close()
            st.rerun()
        else:
            st.error("Invalid Authenticator code.")
    st.stop()

elif not st.session_state.get("user"):
    st.title("Welcome to AI Data Engineering")
    with st.form("auth_form", clear_on_submit=False):
        st.subheader("Authentication")
        username = st.text_input("Username", key="auth_user").strip().lower()
        password = st.text_input("Password", type="password", key="auth_pass").strip()
        
        col1, col2 = st.columns(2)
        login_clicked = col1.form_submit_button("Login", use_container_width=True)
        signup_clicked = col2.form_submit_button("Signup / Register", use_container_width=True)
    
    if st.button("Forgot Password?"):
        st.session_state["forgot_password"] = True
        st.rerun()

    if login_clicked:
        try:
            user = login_user(username, password)
            if user:
                if user.role == "admin":
                    st.session_state["pending_admin"] = user.username
                    st.rerun()
                else:
                    st.session_state["role"] = user.role
                    st.session_state["user"] = user.username
                    _set_auth_url(user.username)
                    st.rerun()
            else:
                st.error("Invalid credentials")
        except PermissionError as pe:
            st.warning(str(pe))

    if signup_clicked:
        st.session_state["signup_mode"] = True
        st.rerun()

    st.stop()


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
            st.pyplot(fig, clear_figure=True)
            # Render Solved metric exactly once
            st.markdown(f"<div style='text-align:center'><b>{solved} / {total}</b><br>Solved</div>", unsafe_allow_html=True)
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
        st.dataframe(recent_runs, use_container_width=True, hide_index=True)

# --- Main Application Logic (Only reached if st.session_state["user"] is set) ---
if st.session_state.get("user"):
    # --- Main App (Only reached if authenticated)
    with st.sidebar:
        components.html(f"""
            <script>
            try {{
                localStorage.setItem('ai_data_user', '{st.session_state["user"]}');
                localStorage.setItem('ai_data_user_ts', Date.now().toString());
            }} catch(e) {{}}
            </script>
        """, height=0)

        st.write(f"User: **{st.session_state['user']}** ({st.session_state.get('role')})")
        if st.button("Logout"):
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

    st.sidebar.markdown("### Navigation")
    visible_sections = [s for s in SECTION_ORDER if s != ADMIN_SECTION_LABEL or st.session_state.get("role") == "admin"]

    module = st.sidebar.selectbox(
        "Choose Section",
        visible_sections,
        index=visible_sections.index(selected_module) if selected_module in visible_sections else 0,
        label_visibility="visible",
    )

    st.session_state["module"] = module
    st.query_params["module"] = module

    # Map labels to rendering functions
    ROUTER = {
        DASHBOARD_SECTION_LABEL: render_dashboard,
        CODING_SECTION_LABEL: lambda: __import__("modules.coding.ui", fromlist=["render_coding"]).render_coding(),
        CONCEPTS_SECTION_LABEL: lambda: __import__("modules.concepts.ui", fromlist=["render_concepts"]).render_concepts(),
        GENAI_SECTION_LABEL: lambda: __import__("modules.genai.ui", fromlist=["render_genai"]).render_genai(),
        SPARK_SECTION_LABEL: lambda: __import__("modules.spark.ui", fromlist=["render_spark"]).render_spark(),
        DATA_MODELING_SECTION_LABEL: lambda: __import__("modules.datamodeling.ui", fromlist=["render_datamodeling"]).render_datamodeling(),
        PROJECTS_SECTION_LABEL: lambda: __import__("modules.projects.ui", fromlist=["render_projects"]).render_projects(),
        ADMIN_SECTION_LABEL: lambda: __import__("modules.admin.ui", fromlist=["render_admin"]).render_admin(),
    }

    if module in ROUTER:
        ROUTER[module]()
