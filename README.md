# AI_Data_Engg
Deployment of complete preparation of Gen AI Data Engg Roles

## Job alerts

The Job Alerts section monitors 550 verified public product-company career
sources for AI Data Engineer and related mid-level roles. More than 200 sources
currently publish remote positions. It keeps India onsite/hybrid roles and
remote roles visible even when an employer specifies a country restriction, so
the candidate can review eligibility. Matching jobs remain in the active feed
for seven days and can be marked Applied.

Run one scan:

```bash
python scripts/run_job_scanner.py
```

Run staggered due-source batches continuously:

```bash
python scripts/run_job_scanner.py --loop --interval-hours 1
```

The scanner uses the same `DATABASE_URL` as the Streamlit application. Run the
continuous command as a separate service; Streamlit is not the scheduler.

## Playwright application preparation

Job cards can queue a browser worker that fills high-confidence fields from an
encrypted Application Profile, uploads the stored resume, and captures the
completed page for review. A separate explicit approval is required before the
worker can press a narrowly matched final submission control. CAPTCHA, MFA,
legal declarations, demographic questions, and unknown required fields are
reported for manual attention and prevent approval.

Generate the required encryption key and keep it stable:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Set the output as `APP_DATA_ENCRYPTION_KEY`. Losing or changing this key makes
the encrypted profile, resume, and preparation results unreadable.

For local development, install Chromium once and run the worker:

```bash
python -m playwright install chromium
python scripts/run_application_agent.py --loop
```

The worker and Streamlit process must use the same `DATABASE_URL`,
`APP_DATA_ENCRYPTION_KEY`, and Playwright artifacts directory.

Existing career-site logins can be added from Application Profile. They are
encrypted and matched only to the exact hostname entered. The worker may submit
a password form to establish the saved browser session. It can submit a job
application only after the corresponding prepared draft is explicitly
approved. Rotate a stored password immediately if the server or encryption key
is compromised.

## Docker

Copy `.env.example` to `.env`, replace the PostgreSQL password, generate the
encryption key, and then start the stack:

```bash
docker compose up --build -d
```

The Compose stack contains PostgreSQL, Streamlit, the hourly job scanner, and a
dedicated Playwright worker. PostgreSQL initializes the `ai_data_engg` and
`upsc_platform_data` databases. Named volumes persist PostgreSQL data, browser
sessions, and application-review screenshots. The Playwright container uses a
2 GB shared-memory allocation to keep Chromium stable.

`.github/workflows/docker-publish.yml` builds both Dockerfiles for pull
requests and publishes `-app` and `-agent` images to GHCR after a push to the
default branch or a version tag.

### Automated scans before home-server deployment

`.github/workflows/job-scan.yml` runs hourly and refreshes only a small due
batch. Every source is targeted approximately once per 12 hours without all
career sites being hit together. The workflow also supports manual runs from
GitHub Actions. Add the PostgreSQL connection URL used by Streamlit as a GitHub
repository Actions secret named `DATABASE_URL`. The workflow writes job matches
to that database, and Streamlit reads them from the Job Alerts section.
