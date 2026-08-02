# AI_Data_Engg
Deployment of complete preparation of Gen AI Data Engg Roles

## Job alerts

The Job Alerts section monitors 240+ verified public product-company career
sources for AI Data Engineer and related mid-level roles. It keeps India
onsite/hybrid roles and remote roles that are global, APAC, or otherwise not
country-restricted. Matching jobs remain in the active feed for seven days and
can be marked Saved, Applied, Rejected, or Not Relevant.

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

### Automated scans before home-server deployment

`.github/workflows/job-scan.yml` runs hourly and refreshes only a small due
batch. Every source is targeted approximately once per 12 hours without all
career sites being hit together. The workflow also supports manual runs from
GitHub Actions. Add the PostgreSQL connection URL used by Streamlit as a GitHub
repository Actions secret named `DATABASE_URL`. The workflow writes job matches
to that database, and Streamlit reads them from the Job Alerts section.
