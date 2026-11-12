"""Skill taxonomy, aliases and a small curated knowledge base.

Everything here is local and deterministic. It powers offline analysis and gives
the LLM structured hints when a provider is configured.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# canonical skill -> aliases found in resumes / job posts
SKILL_ALIASES: dict[str, list[str]] = {
    "Python": ["python", "python3"],
    "Java": ["java"],
    "JavaScript": ["javascript", "js", "es6", "ecmascript"],
    "TypeScript": ["typescript", "ts"],
    "C": ["c language"],
    "C++": ["c++", "cpp"],
    "C#": ["c#", "csharp"],
    "Go": ["golang", "go lang"],
    "Rust": ["rust"],
    "Ruby": ["ruby"],
    "PHP": ["php"],
    "Swift": ["swift"],
    "Kotlin": ["kotlin"],
    "Scala": ["scala"],
    "R": ["r programming", "r language"],
    "MATLAB": ["matlab"],
    "SQL": ["sql", "structured query language"],
    "PostgreSQL": ["postgresql", "postgres", "psql"],
    "MySQL": ["mysql", "mariadb"],
    "SQLite": ["sqlite"],
    "MongoDB": ["mongodb", "mongo"],
    "Redis": ["redis"],
    "Elasticsearch": ["elasticsearch", "elastic search"],
    "React": ["react", "reactjs", "react.js"],
    "Next.js": ["nextjs", "next.js"],
    "Vue.js": ["vue", "vuejs", "vue.js"],
    "Angular": ["angular", "angularjs"],
    "Svelte": ["svelte", "sveltekit"],
    "Node.js": ["nodejs", "node.js", "node js", "node"],
    "Express.js": ["express", "expressjs", "express.js"],
    "Django": ["django"],
    "Flask": ["flask"],
    "FastAPI": ["fastapi", "fast api"],
    "Spring Boot": ["spring boot", "springboot", "spring"],
    "ASP.NET": ["asp.net", "dotnet", ".net", "dotnet core"],
    "REST APIs": ["rest api", "restful", "rest apis", "rest"],
    "GraphQL": ["graphql", "apollo"],
    "gRPC": ["grpc"],
    "HTML": ["html", "html5"],
    "CSS": ["css", "css3"],
    "Tailwind CSS": ["tailwind", "tailwindcss"],
    "Sass": ["sass", "scss"],
    "Bootstrap": ["bootstrap"],
    "Redux": ["redux", "redux toolkit"],
    "React Native": ["react native"],
    "Flutter": ["flutter", "dart"],
    "Android": ["android", "android sdk"],
    "iOS": ["ios", "swiftui", "uikit"],
    "Docker": ["docker", "containerization"],
    "Kubernetes": ["kubernetes", "k8s", "eks", "gke"],
    "AWS": ["aws", "amazon web services", "ec2", "s3", "lambda"],
    "Azure": ["azure", "microsoft azure"],
    "GCP": ["gcp", "google cloud", "bigquery", "cloud run"],
    "Linux": ["linux", "ubuntu", "unix", "bash", "shell scripting"],
    "Git": ["git", "github", "gitlab", "bitbucket"],
    "CI/CD": ["ci/cd", "cicd", "continuous integration", "continuous delivery"],
    "Jenkins": ["jenkins"],
    "GitHub Actions": ["github actions"],
    "Terraform": ["terraform", "infrastructure as code", "iac"],
    "Ansible": ["ansible"],
    "Nginx": ["nginx"],
    "Kafka": ["kafka", "apache kafka"],
    "RabbitMQ": ["rabbitmq"],
    "Celery": ["celery"],
    "Microservices": ["microservices", "microservice architecture"],
    "System Design": ["system design", "distributed systems", "scalability"],
    "Data Structures": ["data structures", "dsa"],
    "Algorithms": ["algorithms", "algorithm design"],
    "Machine Learning": ["machine learning", "ml", "supervised learning", "unsupervised learning"],
    "Deep Learning": ["deep learning", "dl", "neural networks", "cnn", "rnn", "transformers"],
    "NLP": ["nlp", "natural language processing", "text mining"],
    "Computer Vision": ["computer vision", "opencv", "image processing"],
    "PyTorch": ["pytorch", "torch"],
    "TensorFlow": ["tensorflow", "keras"],
    "scikit-learn": ["scikit-learn", "sklearn", "scikit learn"],
    "Pandas": ["pandas"],
    "NumPy": ["numpy"],
    "Matplotlib": ["matplotlib", "seaborn"],
    "LLMs": ["llm", "llms", "large language model", "large language models"],
    "LangChain": ["langchain"],
    "LangGraph": ["langgraph"],
    "RAG": ["rag", "retrieval augmented generation", "retrieval-augmented"],
    "Prompt Engineering": ["prompt engineering", "prompt design"],
    "Hugging Face": ["hugging face", "huggingface", "transformers library"],
    "Vector Databases": ["vector database", "vector db", "pinecone", "faiss", "chromadb", "weaviate", "qdrant"],
    "OpenAI API": ["openai api", "gpt-4", "gpt4", "chatgpt api"],
    "Airflow": ["airflow", "apache airflow"],
    "Spark": ["spark", "pyspark", "apache spark"],
    "Hadoop": ["hadoop", "mapreduce"],
    "dbt": ["dbt", "data build tool"],
    "Snowflake": ["snowflake"],
    "Tableau": ["tableau"],
    "Power BI": ["power bi", "powerbi"],
    "Excel": ["excel", "spreadsheets", "google sheets"],
    "Statistics": ["statistics", "statistical analysis", "hypothesis testing", "a/b testing"],
    "Data Visualization": ["data visualization", "data visualisation", "dashboarding"],
    "ETL": ["etl", "elt", "data pipelines", "data pipeline"],
    "Agile": ["agile", "scrum", "kanban"],
    "JIRA": ["jira", "confluence"],
    "Unit Testing": ["unit testing", "unit tests"],
    "pytest": ["pytest"],
    "Jest": ["jest"],
    "Selenium": ["selenium"],
    "Playwright": ["playwright", "cypress"],
    "Figma": ["figma", "wireframing", "prototyping"],
    "UI/UX": ["ui/ux", "user experience", "user interface", "ux design"],
    "Cybersecurity": ["cybersecurity", "cyber security", "penetration testing", "security assessment"],
    "Networking": ["networking", "tcp/ip", "dns"],
    "Blockchain": ["blockchain", "solidity", "web3"],
    "Firebase": ["firebase", "firestore"],
    "Supabase": ["supabase"],
    "Prisma": ["prisma"],
    "Nginx": ["nginx"],
    "Product Management": ["product management", "roadmap planning", "product strategy"],
    "Communication": ["communication", "stakeholder management", "presentation"],
    "Leadership": ["leadership", "team lead", "mentoring", "mentorship"],
    "Problem Solving": ["problem solving", "analytical thinking", "critical thinking"],
    "Collaboration": ["collaboration", "teamwork", "cross-functional"],
    "Time Management": ["time management", "prioritization", "prioritisation"],
    "Adaptability": ["adaptability", "fast-paced environment", "learning agility"],
    "Attention to Detail": ["attention to detail", "detail-oriented", "detail oriented"],
}

# Which aliases belong to soft skills rather than technical skills.
SOFT_SKILLS = {
    "Communication",
    "Leadership",
    "Problem Solving",
    "Collaboration",
    "Time Management",
    "Adaptability",
    "Attention to Detail",
    "Agile",
    "Product Management",
    "UI/UX",
}

SKILL_CATEGORIES: dict[str, str] = {}
for _skill in SKILL_ALIASES:
    if _skill in {"React", "Next.js", "Vue.js", "Angular", "Svelte", "HTML", "CSS", "Tailwind CSS", "Sass", "Bootstrap", "Redux", "Figma", "UI/UX"}:
        SKILL_CATEGORIES[_skill] = "frontend"
    elif _skill in {"Node.js", "Express.js", "Django", "Flask", "FastAPI", "Spring Boot", "ASP.NET", "REST APIs", "GraphQL", "gRPC", "Microservices", "System Design"}:
        SKILL_CATEGORIES[_skill] = "backend"
    elif _skill in {"Python", "Java", "JavaScript", "TypeScript", "C", "C++", "C#", "Go", "Rust", "Ruby", "PHP", "Swift", "Kotlin", "Scala", "R", "MATLAB"}:
        SKILL_CATEGORIES[_skill] = "language"
    elif _skill in {"SQL", "PostgreSQL", "MySQL", "SQLite", "MongoDB", "Redis", "Elasticsearch"}:
        SKILL_CATEGORIES[_skill] = "database"
    elif _skill in {"Docker", "Kubernetes", "AWS", "Azure", "GCP", "Linux", "Git", "CI/CD", "Jenkins", "GitHub Actions", "Terraform", "Ansible", "Nginx"}:
        SKILL_CATEGORIES[_skill] = "devops"
    elif _skill in {"Machine Learning", "Deep Learning", "NLP", "Computer Vision", "PyTorch", "TensorFlow", "scikit-learn", "Pandas", "NumPy", "Matplotlib", "LLMs", "LangChain", "LangGraph", "RAG", "Prompt Engineering", "Hugging Face", "Vector Databases", "OpenAI API", "Spark", "Hadoop", "Airflow", "dbt", "Snowflake", "Tableau", "Power BI", "Statistics", "Data Visualization", "ETL", "Excel"}:
        SKILL_CATEGORIES[_skill] = "data_ai"
    elif _skill in {"React Native", "Flutter", "Android", "iOS"}:
        SKILL_CATEGORIES[_skill] = "mobile"
    elif _skill in {"Data Structures", "Algorithms", "Unit Testing", "pytest", "Jest", "Selenium", "Playwright"}:
        SKILL_CATEGORIES[_skill] = "engineering"
    elif _skill in {"Cybersecurity", "Networking", "Blockchain"}:
        SKILL_CATEGORIES[_skill] = "security"
    else:
        SKILL_CATEGORIES[_skill] = "soft"


@dataclass
class SkillTemplate:
    topics: list[str]
    project: str
    questions: list[str]
    answer_points: list[str] = field(default_factory=list)
    base_hours: float = 4.0


# Curated guidance shown in the gap roadmap and interview prep. No external links
# are generated, so users are never sent to fabricated resources.
SKILL_TEMPLATES: dict[str, SkillTemplate] = {
    "Python": SkillTemplate(
        ["Python syntax and data types", "OOP and modules", "Error handling", "Testing with pytest", "Packaging and virtual environments"],
        "Build a CLI tool that parses a CSV, validates records and writes a summary report with tests.",
        ["How does Python manage memory?", "Explain list vs tuple vs set.", "What are decorators and when do you use them?"],
        ["Reference counting and garbage collection", "Mutability and performance characteristics", "Functions that wrap other functions"],
        6,
    ),
    "JavaScript": SkillTemplate(
        ["ES6+ syntax", "Closures and scope", "Promises and async/await", "DOM and events", "Modules and bundling"],
        "Build a small browser app with fetch, async rendering and error states.",
        ["Explain the event loop.", "What is a closure?", "Difference between == and ===?"],
        ["Call stack, task queue and microtasks", "Lexical scope captured by functions", "Type coercion"],
        6,
    ),
    "TypeScript": SkillTemplate(
        ["Types vs interfaces", "Generics", "Union and intersection types", "Type narrowing", "Strict compiler options"],
        "Convert a JavaScript utility library to strict TypeScript with reusable generics.",
        ["When would you use a generic?", "Explain type narrowing.", "What does unknown mean?"],
        ["Reusable type-safe abstractions", "Control-flow based typing", "Safer alternative to any"],
        5,
    ),
    "React": SkillTemplate(
        ["Components and props", "State and hooks", "Effects and data fetching", "Performance and memoization", "Testing components"],
        "Build a dashboard with routing, API data, loading states and reusable cards.",
        ["How does useState work?", "When do you use useEffect?", "How would you avoid unnecessary re-renders?"],
        ["State triggers re-render", "Synchronizing with external systems", "Memoization and stable references"],
        8,
    ),
    "Next.js": SkillTemplate(
        ["App router", "Server vs client components", "Data fetching and caching", "API routes", "Deployment"],
        "Create a server-rendered job board with dynamic routes and cached data fetching.",
        ["Explain server components.", "How does caching work?", "When would you use an API route?"],
        ["Rendering on the server without client JS", "Request memoization and revalidation", "Server-side secrets and mutations"],
        8,
    ),
    "Node.js": SkillTemplate(
        ["Event loop", "Modules and npm", "Async patterns", "HTTP servers", "Error handling"],
        "Build a REST API with validation, logging and graceful shutdown.",
        ["How does the event loop work?", "How do you handle uncaught errors?", "What is middleware?"],
        ["Non-blocking I/O phases", "Centralized error handling", "Request pipeline"],
        7,
    ),
    "FastAPI": SkillTemplate(
        ["Routing and dependencies", "Pydantic validation", "Async endpoints", "Authentication", "Testing with TestClient"],
        "Build a typed REST API with SQLite persistence, validation and tests.",
        ["How does dependency injection work?", "Why use Pydantic?", "How do you test an endpoint?"],
        ["Depends() composition", "Request/response validation", "TestClient and fixtures"],
        7,
    ),
    "SQL": SkillTemplate(
        ["SELECT and filtering", "Joins", "Aggregations and GROUP BY", "Subqueries and CTEs", "Indexes and query plans"],
        "Design a small schema and write analytical queries with joins and window functions.",
        ["Explain different join types.", "What is an index?", "How would you find duplicate rows?"],
        ["Join semantics and row multiplication", "B-tree lookup trade-offs", "GROUP BY with HAVING"],
        7,
    ),
    "PostgreSQL": SkillTemplate(
        ["Schema design", "Indexes", "Transactions and isolation", "JSONB", "Query optimization"],
        "Model a multi-tenant application schema and optimize three slow queries with EXPLAIN.",
        ["When would you use JSONB?", "Explain transaction isolation levels.", "How do you debug a slow query?"],
        ["Flexible semi-structured data", "Read anomalies and locking", "EXPLAIN ANALYZE and indexes"],
        8,
    ),
    "Docker": SkillTemplate(
        ["Images and layers", "Dockerfiles", "Volumes and networking", "Compose", "Image size and security"],
        "Containerize a FastAPI + Postgres app with Compose and a multi-stage build.",
        ["What is the difference between an image and a container?", "How do you reduce image size?", "Explain volumes."],
        ["Layered filesystem and runtime instances", "Multi-stage builds and slim bases", "Persistent data outside the container"],
        5,
    ),
    "Kubernetes": SkillTemplate(
        ["Pods and deployments", "Services and ingress", "ConfigMaps and secrets", "Scaling and probes", "Debugging"],
        "Deploy a stateless service with probes, resource limits and horizontal scaling.",
        ["What is a pod?", "How do readiness and liveness probes differ?", "How does a service route traffic?"],
        ["Smallest deployable unit", "Traffic readiness vs restart behavior", "Label selectors and endpoints"],
        10,
    ),
    "AWS": SkillTemplate(
        ["IAM basics", "Compute options", "Storage and databases", "Networking", "Cost awareness"],
        "Deploy a small API with object storage and a managed database, using least-privilege IAM.",
        ["How does IAM authorize a request?", "S3 vs EBS?", "When would you use Lambda?"],
        ["Policies, roles and least privilege", "Object vs block storage", "Event-driven compute"],
        10,
    ),
    "Machine Learning": SkillTemplate(
        ["Problem framing", "Train/validation/test splits", "Bias-variance trade-off", "Metrics", "Leakage and overfitting"],
        "Build an end-to-end classifier with proper validation, baseline and error analysis.",
        ["How do you detect overfitting?", "Precision vs recall?", "What is data leakage?"],
        ["Validation curves and regularization", "Metric choice depends on costs", "Information from the target leaking into features"],
        10,
    ),
    "Deep Learning": SkillTemplate(
        ["Neural network basics", "Backpropagation", "Regularization", "Optimizers", "Transfer learning"],
        "Fine-tune a small image or text model and compare against a baseline.",
        ["Explain backpropagation.", "Why do we need activation functions?", "How do you prevent overfitting?"],
        ["Chain rule and gradients", "Non-linearity", "Dropout, augmentation and early stopping"],
        12,
    ),
    "NLP": SkillTemplate(
        ["Tokenization", "Embeddings", "Sequence models", "Evaluation", "Prompting"],
        "Build a resume-to-job similarity tool with embeddings and evaluate it on labelled pairs.",
        ["What is a token?", "How do embeddings capture meaning?", "How would you evaluate a text classifier?"],
        ["Subword units", "Vector spaces and cosine similarity", "Precision, recall and human review"],
        10,
    ),
    "LLMs": SkillTemplate(
        ["Transformer basics", "Context windows", "Prompting", "Function calling", "Hallucination mitigation"],
        "Build a retrieval-augmented assistant and measure grounded-answer accuracy.",
        ["How does an LLM generate text?", "What causes hallucination?", "How do you evaluate an LLM feature?"],
        ["Next-token prediction", "Unsupported generation and weak grounding", "Task-specific evaluation sets"],
        8,
    ),
    "LangChain": SkillTemplate(
        ["Chains and runnables", "Prompt templates", "Output parsers", "Tools", "Tracing"],
        "Build a document Q&A chain with citations and structured output.",
        ["What is a runnable?", "How do you parse structured output?", "How do you debug a chain?"],
        ["Composable invocation interface", "Schema validation and retries", "Tracing and step inspection"],
        6,
    ),
    "LangGraph": SkillTemplate(
        ["State graphs", "Nodes and edges", "Conditional routing", "Checkpointing", "Human-in-the-loop"],
        "Implement a multi-agent workflow with shared typed state and a retry path.",
        ["Why use a graph instead of a chain?", "How does checkpointing help?", "How do you handle a failing node?"],
        ["Cycles and explicit control flow", "Resumable execution", "Error edges and retries"],
        7,
    ),
    "RAG": SkillTemplate(
        ["Chunking", "Embeddings", "Vector search", "Reranking", "Grounded evaluation"],
        "Build a RAG pipeline over documentation with source citations and retrieval metrics.",
        ["How do you choose chunk size?", "What is reranking?", "How do you evaluate retrieval?"],
        ["Context vs precision trade-offs", "Second-stage relevance scoring", "Recall@k and groundedness"],
        9,
    ),
    "LLM": SkillTemplate([], "", [], [], 8),
    "PyTorch": SkillTemplate(
        ["Tensors", "Autograd", "Datasets and loaders", "Training loops", "GPU basics"],
        "Train a small image classifier with a clean training/validation loop.",
        ["How does autograd work?", "Why call zero_grad()?", "How do you move data to GPU?"],
        ["Dynamic computation graph", "Gradient accumulation", "Device management"],
        9,
    ),
    "Pandas": SkillTemplate(
        ["DataFrames and Series", "Selection and filtering", "Groupby and aggregation", "Joins", "Missing data"],
        "Analyze a messy dataset and produce a reproducible cleaning + summary notebook.",
        ["loc vs iloc?", "How do you handle missing values?", "How do you optimize a large groupby?"],
        ["Label vs positional indexing", "Imputation or explicit dropping", "Categorical dtypes and vectorization"],
        5,
    ),
    "NumPy": SkillTemplate(
        ["Arrays and dtypes", "Broadcasting", "Vectorization", "Indexing", "Linear algebra"],
        "Replace slow Python loops with vectorized NumPy operations and benchmark them.",
        ["What is broadcasting?", "Why is vectorization faster?", "View vs copy?"],
        ["Shape alignment rules", "Contiguous memory and SIMD", "Shared vs duplicated memory"],
        4,
    ),
    "Git": SkillTemplate(
        ["Commits and history", "Branching", "Merging and rebasing", "Pull requests", "Conflict resolution"],
        "Contribute to a repository with feature branches, focused commits and a reviewed PR.",
        ["Merge vs rebase?", "How do you resolve a conflict?", "What makes a good commit?"],
        ["History preservation vs linearization", "Manual hunk resolution", "Small atomic changes"],
        4,
    ),
    "REST APIs": SkillTemplate(
        ["Resources and methods", "Status codes", "Validation", "Pagination", "Versioning"],
        "Design and document a versioned REST API for a small domain.",
        ["Which status code for validation errors?", "How do you paginate?", "PUT vs PATCH?"],
        ["422/400 semantics", "Cursor or offset pagination", "Full vs partial replacement"],
        5,
    ),
    "System Design": SkillTemplate(
        ["Requirements and constraints", "Capacity estimation", "Data modeling", "Caching", "Failure modes"],
        "Design a URL shortener and a job board, documenting trade-offs and bottlenecks.",
        ["How would you scale reads?", "Where would you add a cache?", "What happens if a node fails?"],
        ["Load balancing and replication", "Cache-aside and invalidation", "Graceful degradation"],
        12,
    ),
    "Data Structures": SkillTemplate(
        ["Arrays and strings", "Hash maps", "Stacks and queues", "Trees and graphs", "Complexity analysis"],
        "Solve and explain 30 curated problems, writing complexity notes for each.",
        ["Array vs linked list?", "How does a hash map handle collisions?", "BFS vs DFS?"],
        ["Access and insertion trade-offs", "Chaining or open addressing", "Level order vs depth first"],
        12,
    ),
    "Algorithms": SkillTemplate(
        ["Sorting", "Searching", "Dynamic programming", "Greedy", "Graph algorithms"],
        "Implement 10 core algorithms from scratch with tests and complexity analysis.",
        ["Explain binary search invariants.", "When does greedy fail?", "How do you identify a DP problem?"],
        ["Sorted search space", "Local vs global optimality", "Overlapping subproblems"],
        12,
    ),
    "Communication": SkillTemplate(
        ["Structured answers (STAR)", "Concise explanations", "Active listening", "Written updates", "Stakeholder framing"],
        "Record three STAR answers and get feedback on clarity and structure.",
        ["Tell me about a time you explained a complex idea.", "How do you handle disagreement?", "How do you give updates?"],
        ["Situation, task, action, result", "Empathy and evidence", "Audience-appropriate detail"],
        4,
    ),
    "Problem Solving": SkillTemplate(
        ["Clarifying questions", "Decomposition", "Trade-off analysis", "Debugging method", "Verification"],
        "Work through five ambiguous case questions using explicit assumptions and trade-offs.",
        ["How do you approach an unfamiliar problem?", "How do you verify a solution?", "Describe a bug you fixed."],
        ["Clarify, decompose, prioritize", "Edge cases and tests", "Root cause not symptom"],
        6,
    ),
    "Agile": SkillTemplate(
        ["Iterative delivery", "User stories", "Estimation", "Retrospectives", "Backlog refinement"],
        "Plan a two-week iteration with stories, acceptance criteria and a retrospective.",
        ["What makes a good user story?", "How do you estimate work?", "What is the point of a retro?"],
        ["User value and testable criteria", "Relative sizing", "Continuous process improvement"],
        3,
    ),
    "Figma": SkillTemplate(
        ["Frames and components", "Auto layout", "Design tokens", "Prototyping", "Developer handoff"],
        "Redesign a dashboard screen with reusable components and a clickable prototype.",
        ["How do you organize components?", "What is auto layout?", "How do you prepare a handoff?"],
        ["Variants and naming", "Responsive constraints", "Specs, assets and states"],
        6,
    ),
    "CI/CD": SkillTemplate(
        ["Pipeline stages", "Automated tests", "Build artifacts", "Deployment strategies", "Secrets"],
        "Create a pipeline that lints, tests, builds and deploys a container image.",
        ["What belongs in CI vs CD?", "How do you keep secrets safe?", "How do you roll back?"],
        ["Fast feedback vs release automation", "Secret stores and scoping", "Versioned artifacts"],
        6,
    ),
}


def canonicalize_skill(name: str) -> str | None:
    name = (name or "").strip()
    if not name:
        return None
    lower = name.lower()
    for canonical, aliases in SKILL_ALIASES.items():
        if lower == canonical.lower():
            return canonical
        if lower in aliases:
            return canonical
    return None


def alias_pattern(alias: str) -> re.Pattern[str]:
    escaped = re.escape(alias.lower())
    return re.compile(rf"(?<![a-z0-9+#]){escaped}(?![a-z0-9+#])", re.I)


_ALIAS_PATTERNS: list[tuple[str, list[re.Pattern[str]]]] = [
    (canonical, [alias_pattern(a) for a in aliases])
    for canonical, aliases in SKILL_ALIASES.items()
]


def extract_skills(text: str) -> list[str]:
    """Return canonical skills detected in free text, ordered by first appearance."""
    if not text:
        return []
    found: list[tuple[int, str]] = []
    for canonical, patterns in _ALIAS_PATTERNS:
        positions = [m.start() for p in patterns for m in [p.search(text)] if m]
        if positions:
            found.append((min(positions), canonical))
    found.sort(key=lambda item: item[0])
    seen: set[str] = set()
    result: list[str] = []
    for _, skill in found:
        if skill not in seen:
            seen.add(skill)
            result.append(skill)
    return result


def skill_template(skill: str) -> SkillTemplate:
    if skill in SKILL_TEMPLATES:
        t = SKILL_TEMPLATES[skill]
        return SkillTemplate(
            topics=t.topics or [f"Core concepts of {skill}", "Hands-on practice", "Common interview questions"],
            project=t.project or f"Build a small end-to-end project that applies {skill}.",
            questions=t.questions or [f"How have you used {skill} in a project?", f"What are common mistakes with {skill}?"],
            answer_points=t.answer_points or ["Concrete example", "Trade-offs", "Outcome"],
            base_hours=t.base_hours,
        )
    return SkillTemplate(
        topics=[f"Core concepts of {skill}", f"Hands-on exercises with {skill}", f"Common interview questions about {skill}"],
        project=f"Build a small end-to-end project that applies {skill} and document your decisions.",
        questions=[
            f"How have you used {skill} in a real project?",
            f"Explain the most important concepts behind {skill}.",
            f"What are common pitfalls when working with {skill}?",
        ],
        answer_points=["Specific example", "Key concepts", "Trade-offs and outcome"],
        base_hours=4.0,
    )


ROLE_KEYWORDS = {
    "ai_ml": ["machine learning", "deep learning", "ai engineer", "data scientist", "ml engineer", "nlp", "computer vision", "llm"],
    "data": ["data analyst", "data engineer", "business intelligence", "analytics", "etl", "sql"],
    "frontend": ["frontend", "front-end", "react", "ui engineer", "web developer"],
    "backend": ["backend", "back-end", "api engineer", "server", "django", "fastapi", "node"],
    "fullstack": ["full stack", "full-stack", "fullstack"],
    "mobile": ["mobile", "android", "ios", "flutter", "react native"],
    "devops": ["devops", "sre", "platform engineer", "cloud engineer", "infrastructure"],
    "security": ["security", "cybersecurity", "penetration"],
    "design": ["designer", "ux", "ui/ux", "product design"],
    "qa": ["qa", "quality assurance", "test engineer", "sdet"],
    "product": ["product manager", "product owner", "program manager"],
}


def detect_role_category(title: str, text: str = "") -> str:
    haystack = f"{title} {text}".lower()
    for category, keywords in ROLE_KEYWORDS.items():
        if any(k in haystack for k in keywords):
            return category
    return "general"
