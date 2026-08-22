import os
import re
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


FIELD_PATTERNS = (
    ("email", (r"\be-?mail\b",)),
    ("phone", (r"\bphone\b", r"\bmobile\b")),
    ("first_name", (r"\bfirst name\b", r"\bgiven name\b")),
    ("last_name", (r"\blast name\b", r"\bsurname\b", r"\bfamily name\b")),
    ("full_name", (r"\bfull name\b", r"\bcandidate name\b", r"^name$")),
    ("linkedin_url", (r"\blinkedin\b",)),
    ("portfolio_url", (r"\bportfolio\b", r"\bgithub\b", r"\bwebsite\b")),
    (
        "current_location",
        (r"\bcurrent location\b", r"\bcurrent city\b", r"\bcity of residence\b"),
    ),
    ("years_experience", (r"\byears?.*experience\b", r"\bexperience.*years?\b")),
    ("notice_period", (r"\bnotice period\b", r"\bavailable.*start\b")),
    ("current_company", (r"\bcurrent (?:company|employer)\b",)),
    ("expected_salary", (r"\bexpected (?:salary|compensation)\b", r"\bsalary expectation\b")),
    ("current_salary", (r"\bcurrent (?:salary|compensation)\b",)),
    ("requires_sponsorship", (r"\bsponsor", r"\bvisa sponsorship\b")),
    ("work_authorized", (r"\bauthori[sz].*work\b", r"\blegally.*work\b")),
    ("willing_to_relocate", (r"\brelocat",)),
)

RESUME_PATTERN = re.compile(r"\b(resume|résumé|cv|curriculum vitae)\b", re.I)
BLOCKER_TEXT = (
    ("captcha", "CAPTCHA requires manual completion."),
    ("verify you are human", "Human verification requires manual completion."),
    ("two-factor", "Multi-factor authentication requires manual completion."),
    ("verification code", "A verification code requires manual completion."),
)


def _normalized(value):
    return " ".join(str(value or "").lower().split())


def _safe_segment(value):
    value = re.sub(r"[^a-zA-Z0-9_.-]+", "-", str(value or "")).strip("-")
    return value[:80] or "unknown"


def _field_key(text):
    normalized = _normalized(text)
    for key, patterns in FIELD_PATTERNS:
        if any(re.search(pattern, normalized, re.I) for pattern in patterns):
            return key
    return None


def _profile_value(profile, key):
    if key == "first_name":
        return str(profile.get("full_name", "")).strip().split(" ", 1)[0]
    if key == "last_name":
        parts = str(profile.get("full_name", "")).strip().split(" ", 1)
        return parts[1] if len(parts) > 1 else ""
    return str(profile.get(key, "") or "").strip()


def _custom_profile_value(profile, description):
    normalized_description = _normalized(description)
    for line in str(profile.get("custom_answers", "") or "").splitlines():
        question, separator, answer = line.partition("=")
        normalized_question = _normalized(question)
        if (
            separator
            and len(normalized_question) >= 4
            and normalized_question in normalized_description
            and answer.strip()
        ):
            return answer.strip()
    return ""


def _element_description(locator):
    try:
        return locator.evaluate(
            """el => {
                const labels = [];
                if (el.labels) {
                    for (const label of el.labels) labels.push(label.innerText || label.textContent || "");
                }
                const fieldset = el.closest("fieldset");
                const legend = fieldset && fieldset.querySelector("legend");
                const container = el.closest("[role=group], .field, .form-field, .application-question");
                return [
                    ...labels,
                    el.getAttribute("aria-label") || "",
                    el.getAttribute("placeholder") || "",
                    el.getAttribute("name") || "",
                    el.id || "",
                    legend ? (legend.innerText || legend.textContent || "") : "",
                    container ? (container.innerText || container.textContent || "").slice(0, 240) : ""
                ].filter(Boolean).join(" ");
            }"""
        )
    except Exception:
        return ""


def _select_value(locator, value):
    options = locator.locator("option")
    target = _normalized(value)
    for index in range(options.count()):
        option = options.nth(index)
        label = option.inner_text().strip()
        option_value = option.get_attribute("value")
        if _normalized(label) == target:
            locator.select_option(value=option_value)
            return True
    return False


def _fill_controls(frame, profile, resume_path):
    filled = []
    skipped = []
    controls = frame.locator("input, textarea, select")
    for index in range(controls.count()):
        control = controls.nth(index)
        try:
            tag_name = control.evaluate("el => el.tagName.toLowerCase()")
            input_type = _normalized(control.get_attribute("type") or "text")
            if control.is_disabled() or (
                not control.is_visible() and input_type != "file"
            ):
                continue
            description = _element_description(control)
            required = control.get_attribute("required") is not None or (
                _normalized(control.get_attribute("aria-required")) == "true"
            )

            if input_type == "file":
                if resume_path and RESUME_PATTERN.search(description):
                    control.set_input_files(str(resume_path))
                    filled.append({"field": description or "Resume", "answer": Path(resume_path).name})
                elif required:
                    skipped.append({"field": description or "Required file", "reason": "No matching file"})
                continue
            if input_type in {"hidden", "submit", "button", "image", "reset"}:
                continue
            if input_type == "radio":
                key = _field_key(description)
                value = _profile_value(profile, key) if key else ""
                value = value or _custom_profile_value(profile, description)
                option_value = _normalized(control.get_attribute("value"))
                if value and option_value == _normalized(value):
                    control.check()
                    filled.append(
                        {
                            "field": description or key,
                            "answer": value,
                            "profile_key": key,
                        }
                    )
                elif required and not key:
                    skipped.append(
                        {
                            "field": description or "Required selection",
                            "reason": "No trusted profile answer",
                        }
                    )
                continue
            if input_type == "checkbox":
                custom_value = _normalized(
                    _custom_profile_value(profile, description)
                )
                if custom_value in {"yes", "true", "agree", "agreed"}:
                    control.check()
                    filled.append(
                        {
                            "field": description or "Checkbox declaration",
                            "answer": "Yes",
                            "profile_key": "custom_answers",
                        }
                    )
                elif required:
                    skipped.append(
                        {
                            "field": description or "Required declaration",
                            "reason": "Checkbox and radio declarations require review",
                        }
                    )
                continue

            key = _field_key(description)
            value = _profile_value(profile, key) if key else ""
            value = value or _custom_profile_value(profile, description)
            if not value:
                if required:
                    skipped.append(
                        {
                            "field": description or control.get_attribute("name") or "Required field",
                            "reason": "No trusted profile answer",
                        }
                    )
                continue

            if tag_name == "select":
                was_filled = _select_value(control, value)
            else:
                control.fill(value)
                was_filled = True
            if was_filled:
                filled.append({"field": description or key, "answer": value, "profile_key": key})
            elif required:
                skipped.append(
                    {
                        "field": description or key,
                        "reason": f"No exact option matching {value!r}",
                    }
                )
        except Exception as error:
            skipped.append(
                {
                    "field": _element_description(control) or f"Control {index + 1}",
                    "reason": str(error)[:240],
                }
            )
    required_controls = frame.locator("[required], [aria-required=true]")
    for index in range(required_controls.count()):
        control = required_controls.nth(index)
        try:
            input_type = _normalized(control.get_attribute("type") or "text")
            if not control.is_visible() and input_type != "file":
                continue
            if input_type == "radio":
                missing = control.evaluate(
                    """el => {
                        const root = el.form || el.ownerDocument;
                        return !Array.from(root.querySelectorAll("input[type=radio]"))
                            .some(item => item.name === el.name && item.checked);
                    }"""
                )
            elif input_type == "checkbox":
                missing = not control.is_checked()
            else:
                missing = not bool(control.input_value().strip())
            if missing:
                skipped.append(
                    {
                        "field": _element_description(control) or "Required field",
                        "reason": "Required field remains incomplete",
                    }
                )
        except Exception:
            continue
    return filled, skipped


def _enter_application_form(page):
    visible_controls = page.locator(
        "input:not([type=hidden]):not([type=submit]), textarea, select"
    )
    if visible_controls.count():
        return
    apply_links = page.locator(
        "a",
        has_text=re.compile(r"^\s*apply(?: for this job| now)?\s*$", re.I),
    )
    for index in range(min(apply_links.count(), 5)):
        link = apply_links.nth(index)
        if link.is_visible():
            link.click()
            page.wait_for_load_state("domcontentloaded")
            return


def _login_if_required(page, credentials):
    password_inputs = page.locator("input[type=password]:visible")
    page_host = (urlparse(page.url).hostname or "").lower()
    credential_host = str((credentials or {}).get("site_host", "")).lower()
    if (
        not credentials
        or not credential_host
        or page_host != credential_host
        or not password_inputs.count()
    ):
        return False
    password = password_inputs.first
    form = password.locator("xpath=ancestor::form[1]")
    if not form.count():
        return False
    username = form.locator(
        "input[type=email], input[autocomplete=username], "
        "input[name*=email i], input[name*=user i]"
    )
    if not username.count():
        return False
    username.first.fill(str(credentials.get("login_email", "")))
    password.fill(str(credentials.get("password", "")))
    login_submit = form.locator(
        "button[type=submit], input[type=submit]"
    )
    if not login_submit.count():
        return False
    login_submit.first.click()
    try:
        page.wait_for_load_state("domcontentloaded", timeout=15_000)
    except PlaywrightTimeoutError:
        pass
    return True


def _submit_application(page):
    submit_pattern = re.compile(
        r"^\s*(?:submit(?: (?:my|your|this|the))? application|apply for this job)\s*$",
        re.I,
    )
    candidates = page.locator("form button[type=submit], form input[type=submit]")
    for index in range(candidates.count()):
        candidate = candidates.nth(index)
        if not candidate.is_visible() or candidate.is_disabled():
            continue
        label = (
            candidate.inner_text()
            or candidate.get_attribute("value")
            or candidate.get_attribute("aria-label")
            or ""
        )
        if not submit_pattern.match(label):
            continue
        candidate.click()
        try:
            page.wait_for_load_state("domcontentloaded", timeout=15_000)
        except PlaywrightTimeoutError:
            pass
        body_text = _normalized(page.locator("body").inner_text(timeout=10_000))
        confirmation = any(
            marker in body_text
            for marker in (
                "application has been submitted",
                "application received",
                "thank you for applying",
                "thanks for applying",
            )
        ) or any(
            marker in page.url.lower()
            for marker in ("confirmation", "thank-you", "application-submitted")
        )
        return {
            "submit_clicked": True,
            "submitted": True,
            "confirmation_detected": confirmation,
        }
    return {
        "submit_clicked": False,
        "submitted": False,
        "confirmation_detected": False,
    }


def prepare_application(
    official_url,
    profile,
    site_credential=None,
    submit_approved=False,
    resume_path=None,
    screenshot_path=None,
    browser_state_dir=None,
    headless=True,
    timeout_ms=45_000,
):
    if not official_url.startswith(("https://", "http://")):
        raise ValueError("Only HTTP(S) application URLs are supported.")
    state_dir = Path(browser_state_dir or "data/playwright/browser-state")
    state_dir.mkdir(parents=True, exist_ok=True)
    if screenshot_path:
        Path(screenshot_path).parent.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(
            user_data_dir=str(state_dir),
            headless=headless,
            viewport={"width": 1440, "height": 1000},
            accept_downloads=False,
        )
        page = context.pages[0] if context.pages else context.new_page()
        page.set_default_timeout(timeout_ms)
        try:
            page.goto(official_url, wait_until="domcontentloaded")
            login_attempted = _login_if_required(page, site_credential)
            _enter_application_form(page)
            try:
                page.wait_for_load_state("networkidle", timeout=8_000)
            except PlaywrightTimeoutError:
                pass

            blockers = []
            if page.locator("input[type=password]:visible").count():
                blockers.append("Login is required. Authenticate this saved browser session.")
            body_text = _normalized(page.locator("body").inner_text(timeout=10_000))
            for marker, message in BLOCKER_TEXT:
                if marker in body_text:
                    blockers.append(message)

            filled = []
            skipped = []
            for frame in page.frames:
                frame_filled, frame_skipped = _fill_controls(frame, profile, resume_path)
                filled.extend(frame_filled)
                skipped.extend(frame_skipped)

            required_missing = []
            seen_missing = set()
            for item in skipped:
                label = item["field"]
                if label not in seen_missing:
                    required_missing.append(item)
                    seen_missing.add(label)
            if required_missing:
                blockers.append(
                    f"{len(required_missing)} required field(s) need a trusted answer or declaration."
                )
            if not filled:
                blockers.append("No supported application fields were found on this page.")

            submission = {
                "submit_clicked": False,
                "submitted": False,
                "confirmation_detected": False,
            }
            if submit_approved and not blockers:
                submission = _submit_application(page)
                if not submission["submit_clicked"]:
                    blockers.append(
                        "No supported final Submit Application control was found."
                    )
                elif not submission["confirmation_detected"]:
                    blockers.append(
                        "The submission control was clicked, but the site did not show a "
                        "recognizable confirmation. Verify the application history before retrying."
                    )

            if screenshot_path:
                page.screenshot(path=str(screenshot_path), full_page=True)
            return {
                "page_title": page.title(),
                "final_url": page.url,
                "filled_fields": filled,
                "required_attention": required_missing,
                "blockers": list(dict.fromkeys(blockers)),
                "screenshot": str(screenshot_path) if screenshot_path else "",
                "login_attempted": login_attempted,
                **submission,
                "manual_submit_required": not submission["submitted"],
            }
        finally:
            context.close()


def worker_paths(draft_id, username_key, source):
    artifacts_root = Path(
        os.getenv("PLAYWRIGHT_ARTIFACTS_DIR", "data/playwright/artifacts")
    )
    state_root = Path(
        os.getenv("PLAYWRIGHT_STATE_DIR", "data/playwright/browser-state")
    )
    artifact_dir = artifacts_root / f"draft-{int(draft_id)}"
    state_dir = state_root / _safe_segment(username_key) / _safe_segment(source)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    state_dir.mkdir(parents=True, exist_ok=True)
    return {
        "artifact_dir": artifact_dir,
        "screenshot_path": artifact_dir / "review.png",
        "browser_state_dir": state_dir,
    }
