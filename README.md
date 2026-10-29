# IS-Project-TrustScoreAI

## Administrator access

Administrator accounts have their own email and password. There is no public admin sign-up page. To create the first administrator:

1. Activate the project virtual environment and start PostgreSQL.
2. In pgAdmin, connect to `trust_score_ai_db` and run `migrations/add_admin_user_type.sql` in the Query Tool.
3. From this project folder, run `python create_admin.py`. Enter the administrator's name, email, and password when prompted. The password is hidden while typing and stored as a bcrypt hash.
4. Start the API and frontend, then sign in using that administrator email and password.

The administrator dashboard provides organization-wide KPI averages and report category ratings, and lets an admin add, edit, deactivate, and assign employees, supervisors, and executives in the hierarchy. The AI dashboard shows organization-wide Trust Score pipeline results and automatically classified supervisor appraisal answers. Do not run `python load_data.py --reset` after creating accounts unless you intend to drop and rebuild the tables and user accounts.

## Appraisal NLP training

The rebuilt `appraisal_nlp_training_workflow.ipynb` is the clean Colab workflow for the two text models. It validates the adjudicated workbook, creates statement IDs when the workbook does not contain `text_group_id`, groups near-duplicate templates before splitting train/validation/test data, evaluates multi-label competency and direction classification, and exports the model files. The original `appraisal_nlp_baseline_colab.ipynb` should be kept as the historical notebook.

For local training of both appraisal models, activate `venv` and run:

```powershell
python -m pip install -r requirements-training.txt
python train_competency_classifier.py "C:\Users\stacy\Downloads\appraisal_statement_annotation_2000_set.xlsx"
```

The script writes both the competency and direction model files plus their metadata beside `main.py`, using the app environment’s pinned scikit-learn version. The API loads model artifacts at startup, so restart Uvicorn after placing or training them.

Before using the automatic classification endpoint with the updated database schema, run `migrations/20261027_automatic_multilabel_supervisor_classification.sql` in pgAdmin against `trust_score_ai_db`. This migration retains old classification rows as superseded history and changes old runs that were waiting for manual review to incomplete so they can be regenerated.
