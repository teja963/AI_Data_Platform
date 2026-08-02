# AI_Data_Engg
Deployment of complete preparation of Gen AI Data Engg Roles

## Job alerts

The Job Alerts section monitors public Microsoft Careers listings for global and
remote AI Data Engineer and related mid-level roles. Matching jobs are kept in
the active feed for seven days and can be marked Saved, Applied, Rejected, or
Not Relevant.

Run one scan:

```bash
python scripts/run_job_scanner.py
```

Run the scanner continuously at the default 12-hour interval:

```bash
python scripts/run_job_scanner.py --loop
```

The scanner uses the same `DATABASE_URL` as the Streamlit application. Run the
continuous command as a separate service; Streamlit is not the scheduler.

### Automated scans before home-server deployment

`.github/workflows/job-scan.yml` runs automatically at 07:30 and 19:30 IST and
also supports manual runs from GitHub Actions. Add the PostgreSQL connection URL
used by Streamlit as a GitHub repository Actions secret named `DATABASE_URL`.
The workflow writes job matches to that database, and Streamlit reads them from
the Job Alerts section.
