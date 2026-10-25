# IS-Project-TrustScoreAI

## Administrator access

Administrator accounts have their own email and password. There is no public admin sign-up page. To create the first administrator:

1. Activate the project virtual environment and start PostgreSQL.
2. In pgAdmin, connect to `trust_score_ai_db` and run `migrations/add_admin_user_type.sql` in the Query Tool.
3. From this project folder, run `python create_admin.py`. Enter the administrator's name, email, and password when prompted. The password is hidden while typing and stored as a bcrypt hash.
4. Start the API and frontend, then sign in using that administrator email and password.

The administrator dashboard provides organization-wide KPI averages and report category ratings, and lets an admin add, edit, deactivate, and assign employees, supervisors, and executives in the hierarchy. AI category averages are calculated from saved AI appraisal reports; draft ratings remain provisional, and human-reviewed counts are shown separately. Do not run `python load.py --reset` after creating accounts unless you intend to drop and rebuild the tables and user accounts.
