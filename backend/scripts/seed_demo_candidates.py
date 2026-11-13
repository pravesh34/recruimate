"""Seed five demo candidate accounts with distinct resumes and profiles.

Run from the backend directory:

    python scripts/seed_demo_candidates.py

Each candidate gets:
  * a login account (candidate1..candidate5@example.com)
  * a resume profile with genuinely different skills, experience and education
  * a copy of the demo job postings so the ranking has something to score

The script is idempotent: re-running updates the profiles in place.
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

DB_PATH = BACKEND_DIR / "data" / "recruimate.db"

DEMO_PASSWORD = "RecruiMate@123"

CANDIDATES: list[dict] = [
    {
        "email": "candidate1@example.com",
        "display_name": "Aarav Sharma",
        "headline": "B.Tech AI & ML undergraduate seeking ML internships",
        "summary": (
            "Final-year B.Tech student in Artificial Intelligence and Machine Learning at "
            "NIT Sikkim. Built a mixture-of-agents research project on detecting AI "
            "generated text. Comfortable with Python, NumPy, Pandas and scikit-learn."
        ),
        "location": "Sikkim, India",
        "phone": "+91 90000 00001",
        "skills": [
            "Python", "C", "Data Structures and Algorithms", "NumPy", "Pandas",
            "Matplotlib", "Scikit-learn", "Machine Learning", "Deep Learning",
            "Neural Networks", "SQL", "Git",
        ],
        "soft_skills": ["Communication", "Teamwork", "Fast learner"],
        "years_experience": 0.0,
        "education": [
            {
                "degree": "B.Tech",
                "specialization": "Artificial Intelligence and Machine Learning",
                "institution": "National Institute of Technology Sikkim",
                "expected_graduation": "2026",
                "cgpa": "8.1",
                "status": "Final year",
            }
        ],
        "experience": [],
        "projects": [
            {
                "name": "Mixture-of-Experts Detector for AI Text",
                "description": (
                    "Research project on routing short vs long text between specialised "
                    "classifiers, using PyTorch and scikit-learn, evaluated with TF-IDF "
                    "and BM25 features."
                ),
                "technologies": ["Python", "PyTorch", "scikit-learn", "Transformers"],
            },
            {
                "name": "Sentiment Analysis Dashboard",
                "description": (
                    "Built a pandas pipeline over 50k tweets with a scikit-learn classifier "
                    "and a Matplotlib dashboard for weekly trends."
                ),
                "technologies": ["Python", "Pandas", "Matplotlib", "scikit-learn"],
            },
        ],
        "certifications": ["DeepLearning.AI - Machine Learning Specialization (in progress)"],
        "resume_filename": "candidate1_aarav_ai_ml.txt",
    },
    {
        "email": "candidate2@example.com",
        "display_name": "Diya Patel",
        "headline": "Data Scientist with 3 years in retail analytics",
        "summary": (
            "Data scientist with three years of experience in e-commerce analytics. "
            "Owns churn models and a forecasting pipeline serving 40k daily orders. "
            "Strong SQL, Python and experiment design skills."
        ),
        "location": "Mumbai, India",
        "phone": "+91 90000 00002",
        "skills": [
            "Python", "SQL", "Pandas", "NumPy", "Scikit-learn", "Machine Learning",
            "Statistics", "Data Analysis", "Tableau", "Spark", "A/B Testing",
            "Apache Airflow", "AWS", "Git",
        ],
        "soft_skills": ["Stakeholder communication", "Storytelling with data", "Mentoring"],
        "years_experience": 3.0,
        "education": [
            {
                "degree": "M.Sc.",
                "specialization": "Applied Statistics",
                "institution": "Indian Statistical Institute",
                "expected_graduation": "2021",
                "cgpa": "8.9",
                "status": "Completed",
            }
        ],
        "experience": [
            {
                "title": "Data Scientist",
                "company": "CartMagnet",
                "start": "2023-06",
                "end": "Present",
                "description": (
                    "Built churn propensity models in Python and scikit-learn that lifted "
                    "retained revenue by 9%. Designed the Spark ETL feeding a 40k order "
                    "daily warehouse and ran weekly A/B tests with the growth team."
                ),
            },
            {
                "title": "Analytics Engineer",
                "company": "ShopSphere",
                "start": "2021-08",
                "end": "2023-05",
                "description": (
                    "Automated reporting with Airflow and Tableau, cutting manual "
                    "reporting effort by two thirds across four business units."
                ),
            },
        ],
        "projects": [
            {
                "name": "Demand Forecasting Service",
                "description": (
                    "Gradient boosted forecasting models for weekly demand, published "
                    "through an Airflow DAG with Tableau dashboards for category managers."
                ),
                "technologies": ["Python", "Spark", "Airflow", "Tableau"],
            }
        ],
        "certifications": ["AWS Certified Data Analytics - Associate"],
        "resume_filename": "candidate2_diya_data_scientist.txt",
    },
    {
        "email": "candidate3@example.com",
        "display_name": "Arjun Menon",
        "headline": "Backend engineer - Python APIs and distributed systems",
        "summary": (
            "Backend engineer with four years building payment and ledger services in "
            "Python. Runs a multi-region FastAPI stack on Kubernetes with Postgres, "
            "Redis and full CI/CD coverage."
        ),
        "location": "Hyderabad, India",
        "phone": "+91 90000 00003",
        "skills": [
            "Python", "FastAPI", "Django", "REST API", "SQL", "PostgreSQL", "Redis",
            "Docker", "Kubernetes", "CI/CD", "Git", "RabbitMQ", "AWS", "Microservices",
        ],
        "soft_skills": ["Code review culture", "Incident response", "Technical writing"],
        "years_experience": 4.0,
        "education": [
            {
                "degree": "B.E.",
                "specialization": "Computer Engineering",
                "institution": "VIT Vellore",
                "expected_graduation": "2020",
                "cgpa": "8.4",
                "status": "Completed",
            }
        ],
        "experience": [
            {
                "title": "Senior Backend Engineer",
                "company": "Corebank",
                "start": "2022-04",
                "end": "Present",
                "description": (
                    "Owns the payments API handling 30k transactions per day. Migrated a "
                    "monolith to FastAPI microservices on Kubernetes with zero downtime "
                    "and cut p99 latency by 45%."
                ),
            },
            {
                "title": "Backend Engineer",
                "company": "Nimbus Retail",
                "start": "2020-07",
                "end": "2022-03",
                "description": (
                    "Built the order ledger and reconciliation jobs in Python with Postgres "
                    "and RabbitMQ, and introduced CI/CD with full automated test coverage."
                ),
            },
        ],
        "projects": [
            {
                "name": "Idempotent Payment Gateway",
                "description": (
                    "Designed a ledger with idempotency keys so retries never double "
                    "charge, backed by PostgreSQL advisory locks and full audit trails."
                ),
                "technologies": ["Python", "FastAPI", "PostgreSQL", "Redis", "Docker"],
            }
        ],
        "certifications": ["Certified Kubernetes Application Developer (CKAD)"],
        "resume_filename": "candidate3_arjun_backend.txt",
    },
    {
        "email": "candidate4@example.com",
        "display_name": "Ishita Rao",
        "headline": "MLOps engineer - shipping models to production",
        "summary": (
            "MLOps engineer focused on taking models from notebook to production. "
            "Two years owning CI/CD for models, feature stores and monitoring. "
            "Strong Python, Docker and Kubernetes experience."
        ),
        "location": "Bengaluru, India",
        "phone": "+91 90000 00004",
        "skills": [
            "Python", "MLOps", "Docker", "Kubernetes", "CI/CD", "MLflow", "Airflow",
            "AWS", "GCP", "Terraform", "Prometheus", "Grafana", "Git",
            "Model Deployment", "Monitoring",
        ],
        "soft_skills": ["Automation mindset", "Cross-team collaboration", "Documentation"],
        "years_experience": 2.0,
        "education": [
            {
                "degree": "B.Tech",
                "specialization": "Information Technology",
                "institution": "PES University",
                "expected_graduation": "2023",
                "cgpa": "8.2",
                "status": "Completed",
            }
        ],
        "experience": [
            {
                "title": "MLOps Engineer",
                "company": "ScaleForge",
                "start": "2023-09",
                "end": "Present",
                "description": (
                    "Runs the full ML delivery pipeline for eight models: MLflow tracking, "
                    "Airflow orchestration, Docker packaging and Kubernetes deployment with "
                    "Prometheus drift alerts. Cut model release time from two weeks to one day."
                ),
            },
            {
                "title": "Data Engineer",
                "company": "Insighthub",
                "start": "2023-01",
                "end": "2023-08",
                "description": (
                    "Built Terraform modules and CI/CD pipelines for GCP data workloads and "
                    "migrated scheduled jobs to Airflow with data quality checks."
                ),
            },
        ],
        "projects": [
            {
                "name": "Model Drift Monitoring Stack",
                "description": (
                    "Prometheus and Grafana dashboards that track feature and prediction "
                    "drift, with automated rollback when accuracy regresses below threshold."
                ),
                "technologies": ["Python", "Prometheus", "Grafana", "MLflow", "Kubernetes"],
            }
        ],
        "certifications": ["Google Cloud Professional Machine Learning Engineer"],
        "resume_filename": "candidate4_ishita_mlops.txt",
    },
    {
        "email": "candidate5@example.com",
        "display_name": "Kabir Nair",
        "headline": "LLM engineer - evaluation, RAG and prompt systems",
        "summary": (
            "LLM engineer focused on evaluation and retrieval. Ships RAG systems, builds "
            "LLM eval harnesses and tunes prompts for production reliability. Comfortable "
            "with OpenAI, Gemini and open-source transformer models."
        ),
        "location": "Pune, India",
        "phone": "+91 90000 00005",
        "skills": [
            "Python", "LLMs", "RAG", "Prompt Engineering", "Evaluation", "NLP",
            "Hugging Face", "Transformers", "LangChain", "Vector Databases", "FastAPI",
            "PyTorch", "Deep Learning", "Git", "Docker",
        ],
        "soft_skills": ["Rigorous evaluation mindset", "Technical writing", "Curiosity"],
        "years_experience": 2.0,
        "education": [
            {
                "degree": "M.Tech",
                "specialization": "Machine Learning",
                "institution": "IIT Bombay",
                "expected_graduation": "2023",
                "cgpa": "9.0",
                "status": "Completed",
            }
        ],
        "experience": [
            {
                "title": "LLM Engineer",
                "company": "Promptworks",
                "start": "2024-02",
                "end": "Present",
                "description": (
                    "Built the evaluation harness for a production LLM product: golden "
                    "datasets, LLM-as-judge scoring and regression gates in CI. Shipped a "
                    "RAG support assistant that resolved 68% of tickets without a human."
                ),
            },
            {
                "title": "AI Research Assistant",
                "company": "Vector Labs",
                "start": "2023-07",
                "end": "2024-01",
                "description": (
                    "Reproduced transformer architecture experiments on Hugging Face "
                    "models, benchmarking retrieval strategies for long-context QA."
                ),
            },
        ],
        "projects": [
            {
                "name": "LLM Evaluation Harness",
                "description": (
                    "A pytest-based regression suite with golden datasets, judge scoring "
                    "and per-model scorecards that gate releases on quality regression."
                ),
                "technologies": ["Python", "LLMs", "pytest", "Hugging Face"],
            },
            {
                "name": "Hybrid RAG Retrieval",
                "description": (
                    "Combined BM25 lexical search with dense vector retrieval and a "
                    "cross-encoder reranker, improving answer faithfulness by 21%."
                ),
                "technologies": ["Python", "RAG", "Vector Databases", "Transformers"],
            },
        ],
        "certifications": [],
        "resume_filename": "candidate5_kabir_llm.txt",
    },
]


def build_resume_text(c: dict) -> str:
    """Render a readable plain-text resume from the structured profile."""
    lines: list[str] = []
    lines.append(c["display_name"].upper())
    lines.append(c["headline"])
    lines.append("")
    lines.append(f"Email: {c['email']}   Phone: {c['phone']}   Location: {c['location']}")
    lines.append("")
    lines.append("SUMMARY")
    lines.append(c["summary"])
    lines.append("")
    lines.append("SKILLS")
    lines.append(", ".join(c["skills"]))
    lines.append("")
    if c["education"]:
        lines.append("EDUCATION")
        for edu in c["education"]:
            lines.append(
                f"- {edu['degree']} {edu['specialization']}, {edu['institution']} "
                f"(CGPA {edu['cgpa']}, {edu['status']})"
            )
        lines.append("")
    if c["experience"]:
        lines.append("EXPERIENCE")
        for exp in c["experience"]:
            lines.append(f"- {exp['title']}, {exp['company']} ({exp['start']} - {exp['end']})")
            lines.append(f"  {exp['description']}")
        lines.append("")
    if c["projects"]:
        lines.append("PROJECTS")
        for proj in c["projects"]:
            lines.append(f"- {proj['name']}: {proj['description']}")
            lines.append(f"  Tech: {', '.join(proj['technologies'])}")
        lines.append("")
    if c["certifications"]:
        lines.append("CERTIFICATIONS")
        for cert in c["certifications"]:
            lines.append(f"- {cert}")
        lines.append("")
    return "\n".join(lines)


def seed() -> None:
    from app.core.auth import hash_password
    from app.database.models import (
        AuthSession,
        Base,
        JobAnalysis,
        ResumeProfile,
        User,
        engine,
        init_db,
    )
    from app.schemas import CandidateProfile

    init_db()

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    password_hash = hash_password(DEMO_PASSWORD)

    for c in CANDIDATES:
        email = c["email"]

        # --- user account -------------------------------------------------
        cursor.execute("SELECT id FROM users WHERE email = ?", (email,))
        row = cursor.fetchone()
        if row:
            user_id = row[0]
            cursor.execute(
                "UPDATE users SET display_name = ?, password_hash = ?, role = 'candidate', "
                "is_active = 1, is_demo = 1, is_local = 0 WHERE id = ?",
                (c["display_name"], password_hash, user_id),
            )
        else:
            cursor.execute(
                "INSERT INTO users (email, display_name, password_hash, role, is_active, "
                "is_demo, is_local, created_at, updated_at) "
                "VALUES (?, ?, ?, 'candidate', 1, 1, 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)",
                (email, c["display_name"], password_hash),
            )
            user_id = cursor.lastrowid

        # --- resume profile -----------------------------------------------
        profile = {
            "name": c["display_name"],
            "headline": c["headline"],
            "email": email,
            "phone": c["phone"],
            "location": c["location"],
            "summary": c["summary"],
            "skills": c["skills"],
            "soft_skills": c["soft_skills"],
            "education": c["education"],
            "experience": c["experience"],
            "projects": c["projects"],
            "certifications": c["certifications"],
            "achievements": [],
            "resume_strengths": [],
            "resume_weaknesses": [],
            "improvement_suggestions": [],
            "unknown_fields": [],
            "years_experience": c["years_experience"],
        }
        # Validate against the real schema so nothing silently drifts.
        CandidateProfile.model_validate(profile)

        raw_text = build_resume_text(c)

        cursor.execute(
            "SELECT id FROM resume_profiles WHERE user_id = ? AND filename = ?",
            (user_id, c["resume_filename"]),
        )
        row = cursor.fetchone()
        if row:
            cursor.execute(
                "UPDATE resume_profiles SET raw_text = ?, profile = ?, provider = 'demo' WHERE id = ?",
                (raw_text, json.dumps(profile), row[0]),
            )
            resume_id = row[0]
        else:
            cursor.execute(
                "INSERT INTO resume_profiles (user_id, filename, storage_path, raw_text, profile, "
                "provider, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, 'demo', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)",
                (user_id, c["resume_filename"], "", raw_text, json.dumps(profile)),
            )
            resume_id = cursor.lastrowid

        print(f"  {email:<28} user_id={user_id:<3} resume_id={resume_id:<3} {c['display_name']}")

    conn.commit()
    conn.close()
    print(f"\nSeeded {len(CANDIDATES)} demo candidates.")
    print(f"Password for every demo account: {DEMO_PASSWORD}")


if __name__ == "__main__":
    seed()
