"""Demo job postings shared by the seeder and the CLI script."""

DEMO_JOBS: list[dict] = [
    {
        "title": "Machine Learning Engineer",
        "company": "Nexlify AI",
        "location": "Bengaluru, India",
        "url": "https://demo.example.com/jobs/mle",
        "required_skills": ["Python", "Machine Learning", "Deep Learning", "PyTorch"],
        "preferred_skills": ["TensorFlow", "Docker", "AWS", "NLP"],
        "min_years_experience": 2,
        "description": (
            "We are hiring a Machine Learning Engineer to build and ship deep learning "
            "models in production. You will work with Python, PyTorch and TensorFlow to "
            "design training pipelines, tune deep learning models and deploy them with "
            "Docker on AWS. You will collaborate with NLP engineers on text models, "
            "write clean Python code, and participate in code reviews. Experience with "
            "machine learning in production environments is required. 2+ years of "
            "relevant experience is preferred."
        ),
    },
    {
        "title": "AI Research Intern",
        "company": "Vector Labs",
        "location": "Remote (India)",
        "url": "https://demo.example.com/jobs/ai-research-intern",
        "required_skills": ["Python", "Machine Learning", "Deep Learning", "Research"],
        "preferred_skills": ["PyTorch", "NLP", "Hugging Face", "Transformers"],
        "min_years_experience": 0,
        "description": (
            "Vector Labs is hiring an AI Research Intern to support our research team. "
            "You will implement and evaluate deep learning models in Python, reproduce "
            "state of the art NLP and Transformer papers, run experiments on PyTorch and "
            "Hugging Face models, and help document findings. Prior coursework in machine "
            "learning and deep learning is required. This is a research focused role with "
            "mentorship from senior researchers. No prior professional experience needed."
        ),
    },
    {
        "title": "LLM Evaluation Specialist",
        "company": "Promptworks",
        "location": "Remote",
        "url": "https://demo.example.com/jobs/llm-evaluation",
        "required_skills": ["Python", "LLMs", "Prompt Engineering", "Evaluation"],
        "preferred_skills": ["Deep Learning", "NLP", "Data Analysis", "Hugging Face"],
        "min_years_experience": 1,
        "description": (
            "As an LLM Evaluation Specialist you will design and run evaluation suites for "
            "large language models. You will write Python scripts, build prompt evaluation "
            "pipelines, and produce data analysis reports on model quality. You will use "
            "prompt engineering techniques, compare open source and hosted LLMs, and "
            "collaborate with the research team on deep learning evaluation. 1+ years of "
            "experience with language models is required."
        ),
    },
    {
        "title": "Data Scientist",
        "company": "Insight Retail",
        "location": "Mumbai, India",
        "url": "https://demo.example.com/jobs/data-scientist",
        "required_skills": ["Python", "SQL", "Pandas", "Data Analysis", "Machine Learning"],
        "preferred_skills": ["Tableau", "Spark", "AWS", "Scikit-learn"],
        "min_years_experience": 2,
        "description": (
            "Data Scientist role focused on customer analytics for our retail business. "
            "You will write SQL queries, build Pandas pipelines, apply machine learning "
            "models with Scikit-learn, and create dashboards in Tableau. You will perform "
            "data analysis on large datasets using Spark on AWS. 2+ years of experience is "
            "required and you must be comfortable communicating findings to non technical "
            "stakeholders."
        ),
    },
    {
        "title": "Backend Engineer (Python)",
        "company": "Corebank",
        "location": "Hyderabad, India",
        "url": "https://demo.example.com/jobs/backend-python",
        "required_skills": ["Python", "SQL", "Docker", "REST API", "Git"],
        "preferred_skills": ["FastAPI", "PostgreSQL", "Redis", "Kubernetes"],
        "min_years_experience": 3,
        "description": (
            "We need a Backend Engineer to build and operate our payments APIs. You will "
            "write Python services, design REST API endpoints, use SQL and PostgreSQL for "
            "persistence, and containerise services with Docker. Experience with Git, "
            "Redis and Kubernetes is a plus. 3+ years of backend engineering experience is "
            "required. You will own services end to end including testing and deployment."
        ),
    },
    {
        "title": "Full Stack Developer",
        "company": "ShopSphere",
        "location": "Remote",
        "url": "https://demo.example.com/jobs/fullstack",
        "required_skills": ["JavaScript", "React", "Node.js", "SQL", "Git"],
        "preferred_skills": ["TypeScript", "Python", "Docker", "AWS"],
        "min_years_experience": 2,
        "description": (
            "Full Stack Developer wanted to build customer facing web applications. You "
            "will build React front ends, write Node.js services, and work with SQL "
            "databases. Git, Docker and AWS experience is preferred. 2+ years of full "
            "stack development experience is required. Python is a plus for internal "
            "tooling work."
        ),
    },
    {
        "title": "Deep Learning Engineer",
        "company": "Visionary Labs",
        "location": "Pune, India",
        "url": "https://demo.example.com/jobs/deep-learning-engineer",
        "required_skills": ["Python", "Deep Learning", "PyTorch", "Computer Vision", "Machine Learning"],
        "preferred_skills": ["TensorFlow", "CUDA", "Docker", "MLOps"],
        "min_years_experience": 3,
        "description": (
            "Deep Learning Engineer role focused on computer vision models. You will train "
            "and optimise PyTorch and TensorFlow models, work with CUDA for GPU training, "
            "and deploy models with Docker. Strong machine learning and deep learning "
            "fundamentals required. 3+ years of experience with production computer vision "
            "systems is required. MLOps tooling experience is a strong plus."
        ),
    },
    {
        "title": "AI Solutions Consultant",
        "company": "Nova Consulting",
        "location": "New Delhi, India",
        "url": "https://demo.example.com/jobs/ai-consultant",
        "required_skills": ["Python", "Machine Learning", "Communication", "Data Analysis"],
        "preferred_skills": ["Deep Learning", "LLMs", "SQL", "Tableau"],
        "min_years_experience": 1,
        "description": (
            "AI Solutions Consultant will work with enterprise clients to design machine "
            "learning solutions. You will analyse business data, prototype models in Python, "
            "and present recommendations to stakeholders. Strong communication and data "
            "analysis skills are required. 1+ years of consulting or analytics experience "
            "is required. Familiarity with LLMs and deep learning is preferred."
        ),
    },
]
