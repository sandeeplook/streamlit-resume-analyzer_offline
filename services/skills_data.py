"""Static keyword data used by the rule-based analyzer (no AI/API involved)."""

SKILLS = [
    # Programming languages
    "Python", "Java", "JavaScript", "TypeScript", "C++", "C#", "C", "Go", "Rust",
    "Ruby", "PHP", "Swift", "Kotlin", "Scala", "R", "MATLAB", "Perl", "Objective-C",
    # Web / frontend
    "React", "Angular", "Vue", "Next.js", "HTML", "CSS", "Sass", "Tailwind",
    "Redux", "Webpack", "jQuery", "Bootstrap",
    # Backend / frameworks
    "Node.js", "Express", "Django", "Flask", "FastAPI", "Spring", "Spring Boot",
    ".NET", "ASP.NET", "Ruby on Rails", "Laravel",
    # Data / ML
    "SQL", "NoSQL", "MySQL", "PostgreSQL", "MongoDB", "Redis", "Cassandra",
    "Machine Learning", "Deep Learning", "Data Science", "Data Analysis",
    "Pandas", "NumPy", "Scikit-learn", "TensorFlow", "PyTorch", "Keras",
    "Natural Language Processing", "Computer Vision", "Data Visualization",
    "Tableau", "Power BI", "Excel", "Statistics", "A/B Testing", "Big Data",
    "Spark", "Hadoop", "ETL", "Airflow", "Snowflake", "Data Warehousing",
    # Cloud / DevOps
    "AWS", "Azure", "GCP", "Google Cloud", "Docker", "Kubernetes", "Terraform",
    "Jenkins", "CI/CD", "Ansible", "Linux", "Bash", "Shell Scripting",
    "Git", "GitHub", "GitLab", "Microservices", "REST API", "GraphQL",
    "Serverless", "Lambda", "DevOps", "Site Reliability Engineering",
    # Mobile
    "iOS", "Android", "React Native", "Flutter", "Xamarin",
    # Project / product management
    "Agile", "Scrum", "Kanban", "Jira", "Confluence", "Product Management",
    "Project Management", "Stakeholder Management", "Roadmapping",
    "Requirements Gathering", "Risk Management", "Budgeting",
    # Business / soft-ish (still resume-searchable) skills
    "Leadership", "Team Management", "Cross-functional Collaboration",
    "Communication", "Problem Solving", "Negotiation", "Public Speaking",
    "Strategic Planning", "Customer Relationship Management", "CRM",
    "Salesforce", "SAP", "Business Analysis", "Financial Modeling",
    "Forecasting", "Marketing", "SEO", "SEM", "Content Marketing",
    "Digital Marketing", "Email Marketing", "Social Media Marketing",
    "Copywriting", "Graphic Design", "UI/UX Design", "Figma", "Sketch",
    "Adobe Photoshop", "Adobe Illustrator", "Video Editing",
    # Security / QA
    "Cybersecurity", "Penetration Testing", "Network Security",
    "Quality Assurance", "Test Automation", "Selenium", "Manual Testing",
    "Unit Testing", "Performance Testing",
    # Other common
    "Machine Learning Operations", "MLOps", "Blockchain", "IoT",
    "Supply Chain Management", "Logistics", "Six Sigma", "Lean",
    "Human Resources", "Recruiting", "Payroll", "Accounting", "Auditing",
    "Taxation", "Bookkeeping",
]

CERTIFICATION_KEYWORDS = [
    "PMP", "PRINCE2", "CPA", "CFA", "CIA", "ACCA", "Chartered Accountant",
    "AWS Certified", "AWS Solutions Architect", "AWS Certified Developer",
    "Azure Certified", "Microsoft Certified", "Google Cloud Certified",
    "Certified Kubernetes Administrator", "CKA", "CKAD",
    "Certified Scrum Master", "CSM", "PMI-ACP", "Six Sigma",
    "Lean Six Sigma", "ITIL", "CISSP", "CISA", "CISM", "CEH",
    "Certified Ethical Hacker", "CompTIA Security+", "CompTIA A+",
    "Certified Information Systems Security Professional",
    "SHRM-CP", "SHRM-SCP", "CPHR", "Salesforce Certified",
    "Oracle Certified", "Certified Kubernetes Security Specialist",
    "Google Analytics Certified", "HubSpot Certified", "Tableau Certified",
    "Certified Public Accountant", "Certified Financial Planner", "CFP",
    "Certified ScrumMaster", "TOGAF", "Certified Data Professional",
]

DEGREE_KEYWORDS = [
    "Bachelor of Science", "Bachelor of Engineering", "Bachelor of Technology",
    "Bachelor of Arts", "Bachelor of Business Administration", "B.Tech",
    "B.E.", "BE ", "B.Sc", "BSc", "BBA", "B.Com", "BCom", "BS ", "B.A.",
    "Master of Science", "Master of Engineering", "Master of Technology",
    "Master of Business Administration", "MBA", "M.Tech", "M.E.", "ME ",
    "M.Sc", "MSc", "MS ", "M.A.", "M.Com", "MCom",
    "PhD", "Ph.D.", "Doctorate", "Doctor of Philosophy",
    "Associate Degree", "Diploma", "Postgraduate Diploma", "PGDM",
]

# Words to ignore when extracting "significant" keywords from a job description.
STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "if", "then", "so", "of", "to", "in",
    "on", "at", "for", "with", "by", "from", "up", "about", "into", "over",
    "after", "is", "are", "was", "were", "be", "been", "being", "have", "has",
    "had", "do", "does", "did", "will", "would", "shall", "should", "can",
    "could", "may", "might", "must", "this", "that", "these", "those", "it",
    "its", "as", "we", "you", "your", "our", "their", "they", "he", "she",
    "his", "her", "them", "i", "us", "not", "no", "yes", "than", "such",
    "role", "job", "company", "candidate", "candidates", "team", "work",
    "working", "years", "year", "experience", "experienced", "required",
    "requirement", "requirements", "preferred", "ability", "strong",
    "excellent", "good", "knowledge", "skills", "skill", "responsibilities",
    "responsible", "qualifications", "qualification", "plus", "etc",
    "including", "include", "includes", "across", "within", "any", "all",
    "each", "other", "some", "more", "most", "also", "well", "new", "using",
    "use", "used", "including", "looking", "seeking", "join", "opportunity",
    "position", "apply", "applicant", "applicants", "who", "what", "when",
    "where", "why", "how",
}
