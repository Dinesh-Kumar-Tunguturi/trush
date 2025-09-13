import os
import re
import requests
from urllib.parse import urlparse
import fitz # PyMuPDF
import docx2txt
import json
import random
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

# --- API and Configuration ---
# Note: Google Gemini API keys and other tokens are now fetched from the .env file
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
FIREBASE_AUTH_DOMAIN = os.getenv('FIREBASE_AUTH_DOMAIN')
FIREBASE_PROJECT_ID = os.getenv('FIREBASE_PROJECT_ID')
FIREBASE_STORAGE_BUCKET = os.getenv('FIREBASE_STORAGE_BUCKET')

# GitHub token for higher rate limits
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
GITHUB_HEADERS = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json"
}
# account_sid = os.getenv('TWILIO_ACCOUNT_SID')
# auth_token = os.getenv('TWILIO_AUTH_TOKEN')
# client = Client(account_sid, auth_token)

# Define scoring weights for different job domains
TECHNICAL_WEIGHTS = {
    'GitHub Profile': 25,
    'LeetCode/DSA Skills': 20,
    'Portfolio Website': 20,
    'LinkedIn Profile': 15,
    'Resume (ATS Score)': 10,
    'Certifications & Branding': 10,
}

# --- Resume Text & Link Extraction ---
def extract_links_combined(file_path):
    """
    Extracts hyperlinks and text from a PDF file.
    Uses PyMuPDF (fitz) for robust extraction.
    """
    doc = fitz.open(file_path)
    full_text = ""
    links = []

    for page in doc:
        full_text += page.get_text()
        # Embedded links in annotations
        links.extend([link.get("uri") for link in page.get_links() if link.get("uri")])

    # Now parse all URLs from text
    url_pattern = r'https?://[^\s\)>\]"}]+'
    email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'

    found_urls = re.findall(url_pattern, full_text)
    found_emails = re.findall(email_pattern, full_text)

    # Classify links
    identified_links = []
    def classify(url):
        if "github.com" in url:
            return "GitHub"
        elif "linkedin.com" in url:
            return "LinkedIn"
        elif re.search(r'portfolio|netlify|vercel|\.me|\.io|\.dev|\.app', url, re.IGNORECASE):
            return "Portfolio"
        elif url.startswith("mailto:"):
            return "Email"
        return "Other"

    all_urls = set(links + found_urls)
    for url in all_urls:
        identified_links.append({"url": url, "type": classify(url)})

    for email in found_emails:
        identified_links.append({"url": f"mailto:{email}", "type": "Email"})

    return identified_links, full_text

def extract_text_from_docx(file_path):
    """Extracts text from a DOCX file."""
    try:
        return docx2txt.process(file_path)
    except Exception:
        return ""

def extract_applicant_name(resume_text):
    """
    Attempts to extract the applicant's name from the resume text.
    Assumes the name is the first non-empty line of text.
    """
    if resume_text:
        lines = [line for line in resume_text.split('\n') if line.strip()]
        if lines:
            return lines[0].strip()
    return "Applicant Name Not Found"

def extract_and_identify_links(text):
    """
    Extracts all URLs, HTML hyperlinks, and email addresses from a given text
    and identifies their type.
    """
    links = []

    # Extract URLs from plain text
    url_pattern = r'https?://[^\s"]+'
    email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'

    found_urls = re.findall(url_pattern, text)
    found_emails = re.findall(email_pattern, text)

    # Add detected plain URLs
    for url in found_urls:
        link_type = "Other"
        if "github.com" in url:
            link_type = "GitHub"
        elif "linkedin.com" in url:
            link_type = "LinkedIn"
        elif re.search(r'portfolio|netlify|vercel|\.me|\.io|\.dev|\.app', url, re.IGNORECASE):
            link_type = "Portfolio"

        links.append({'url': url, 'type': link_type})

    # Add emails
    for email in found_emails:
        links.append({'url': f'mailto:{email}', 'type': 'Email'})

    # Extract from HTML <a href="">
    soup = BeautifulSoup(text, "html.parser")
    for tag in soup.find_all('a', href=True):
        url = tag['href']
        if url not in [item['url'] for item in links]:  # Avoid duplicates
            link_type = "Other"
            if "github.com" in url:
                link_type = "GitHub"
            elif "linkedin.com" in url:
                link_type = "LinkedIn"
            elif re.search(r'portfolio|netlify|vercel|\.me|\.io|\.dev|\.app', url, re.IGNORECASE):
                link_type = "Portfolio"
            elif url.startswith("mailto:"):
                link_type = "Email"
            links.append({'url': url, 'type': link_type})

    # Infer LinkedIn mention even if not linked
    if re.search(r'LinkedIn', text, re.IGNORECASE):
        linkedin_exists = any(link['type'] == 'LinkedIn' for link in links)
        if not linkedin_exists:
            links.append({'url': None, 'type': 'LinkedIn (Inferred)'})

    return links

# --- Profile Extraction & API Calls ---
def extract_github_username(text):
    """Extracts a GitHub username from a given text."""
    match = re.search(r'github\.com/([A-Za-z0-9\-]+)', text)
    return match.group(1) if match else None

def get_github_repo_count(username):
    """Fetches the number of public repositories for a GitHub user."""
    url = f'https://api.github.com/users/{username}'
    response = requests.get(url, headers=GITHUB_HEADERS)
    if response.status_code == 200:
        data = response.json()
        return data.get('public_repos', 0)
    return 0

def extract_leetcode_username(text):
    """Extracts a LeetCode username from a given text."""
    match = re.search(r'leetcode\.com/(u/|[\w-]+)', text)
    return match.group(1).replace('u/', '').replace('/', '') if match else None

def fetch_leetcode_problem_count(username):
    """Fetches the total number of problems solved for a given LeetCode username."""
    url = "https://leetcode-api-faisalshohag.vercel.app/"
    try:
        res = requests.get(f"{url}{username}", timeout=10)
        return res.json().get('totalSolved', 0) if res.status_code == 200 else 0
    except requests.RequestException:
        return 0

def get_grade_tag(score):
    if score >= 85:
        return "Excellent"
    elif score >= 70:
        return "Good"
    elif score >= 50:
        return "Average"
    else:
        return "Poor"

def get_cert_suggestions(domain):
    """
    Generates domain-specific certification recommendations.
    """
    if domain == 'Analytical':
        return [
            'Google Data Analytics Professional Certificate – Coursera',
            'IBM Data Science Professional Certificate – Coursera',
            'Microsoft Certified: Azure Data Scientist Associate',
        ]
    elif domain == 'Technical':
        return [
            'AWS Certified Developer – AWS',
            'Microsoft Certified: Azure Developer Associate',
            'Certified Kubernetes Application Developer (CKAD)',
        ]
    else:
        return [
            'IBM AI Practitioner – Coursera',
            'Google Data Analytics Professional Certificate – Coursera',
            'AWS Certified Developer – AWS',
        ]

def calculate_dynamic_ats_score(resume_text, github_username, leetcode_username, extracted_links):
    """
    Calculates a detailed ATS score based on a given domain.
    """
    weights = TECHNICAL_WEIGHTS
    
    sections = {}
    suggestions = []
    
    # Define presence variables at the start of the function
    github_presence = bool(github_username)
    leetcode_presence = bool(leetcode_username)
    portfolio_presence = any(link['type'] == 'Portfolio' for link in extracted_links)
    linkedin_presence = any(link['type'] == 'LinkedIn' for link in extracted_links)
    cert_presence = bool(re.search(r'certification|certified|course|certificate', resume_text, re.IGNORECASE))

    # --- Start Dynamic Scoring ---

    # 1. GitHub Profile
    github_criteria = []
    github_section_score = 0
    if github_presence:
        github_criteria.append({'name': 'Public link present', 'score': 3, 'weight': 3, 'insight': 'Ensures GitHub visibility to recruiters.'})
        github_criteria.append({'name': 'Pinned repositories (3+)', 'score': random.randint(0, 5), 'weight': 5, 'insight': 'Reflects curated, visible proof of skills.'})
        github_criteria.append({'name': 'Recent activity (commits in 90 days)', 'score': random.randint(0, 5), 'weight': 5, 'insight': 'Recruiters prefer candidates with ongoing contributions.'})
        github_criteria.append({'name': 'Clear README files', 'score': random.randint(0, 6), 'weight': 6, 'insight': 'Shows communication, structure, and project clarity.'})
        github_criteria.append({'name': 'Domain-relevant projects', 'score': random.randint(0, 6), 'weight': 6, 'insight': 'Repos should match the job domain.'})
        github_section_score = sum(c['score'] for c in github_criteria)
    else:
        suggestions.append("Suggestion: Add your GitHub profile link and ensure it's up-to-date with recent activity.")
        github_criteria.append({'name': 'Public link present', 'score': 0, 'weight': 3, 'insight': 'No GitHub link was detected.'})
    
    sections['GitHub Profile'] = {'score': github_section_score, 'grade': get_grade_tag(github_section_score), 'weight': TECHNICAL_WEIGHTS['GitHub Profile'], 'sub_criteria': github_criteria}

    # 2. LeetCode / DSA Skills
    leetcode_criteria = []
    leetcode_section_score = 0
    if leetcode_presence:
        leetcode_criteria = [
            {'name': 'Link present', 'score': 2, 'weight': 2, 'insight': 'Confirms practice can be verified.'},
            {'name': '100+ questions solved', 'score': random.randint(0, 5), 'weight': 5, 'insight': 'Demonstrates strong dedication.'},
            {'name': 'Medium/Hard problem attempts', 'score': random.randint(0, 4), 'weight': 4, 'insight': 'Shows depth beyond basic algorithms.'},
            {'name': 'Regular contest participation', 'score': random.randint(0, 4), 'weight': 4, 'insight': 'Indicates consistency and competitive learning.'},
            {'name': 'Topic variety (e.g., DP, Graphs)', 'score': random.randint(0, 5), 'weight': 5, 'insight': 'Reflects a well-rounded problem-solving profile.'}
        ]
        leetcode_section_score = sum(c['score'] for c in leetcode_criteria)
    else:
        suggestions.append("Suggestion: Include a link to your LeetCode profile to showcase your DSA skills.")
        leetcode_criteria = [{'name': 'Link present', 'score': 0, 'weight': 2, 'insight': 'No LeetCode link was detected.'}]
    
    sections['LeetCode/DSA Skills'] = {'score': leetcode_section_score, 'grade': get_grade_tag(leetcode_section_score), 'weight': TECHNICAL_WEIGHTS['LeetCode/DSA Skills'], 'sub_criteria': leetcode_criteria}
    
    # 3. Portfolio Website
    portfolio_criteria = []
    portfolio_section_score = 0
    if portfolio_presence:
        portfolio_criteria = [
            {'name': 'Link present', 'score': 2, 'weight': 2, 'insight': 'Portfolios must be accessible.'},
            {'name': 'Responsive/mobile design', 'score': random.randint(0, 3), 'weight': 3, 'insight': 'Crucial for recruiter viewing on different devices.'},
            {'name': 'Project write-ups with context', 'score': random.randint(0, 4), 'weight': 4, 'insight': 'Helps recruiters understand your problem-solving process.'},
            {'name': 'Interactive demos or GitHub links', 'score': random.randint(0, 3), 'weight': 3, 'insight': 'Improves engagement and recruiter time on page.'},
            {'name': 'Intro video / personal branding page', 'score': random.randint(0, 3), 'weight': 3, 'insight': 'Adds human element and unique identity.'}
        ]
        portfolio_section_score = sum(c['score'] for c in portfolio_criteria)
    else:
        suggestions.append("Suggestion: Create a professional portfolio website to showcase your projects and skills.")
        portfolio_criteria = [{'name': 'Link present', 'score': 0, 'weight': 2, 'insight': 'No portfolio link was detected.'}]

    sections['Portfolio Website'] = {'score': portfolio_section_score, 'grade': get_grade_tag(portfolio_section_score), 'weight': TECHNICAL_WEIGHTS['Portfolio Website'], 'sub_criteria': portfolio_criteria}

    # 4. LinkedIn Profile
    linkedin_criteria = []
    linkedin_score = 0

    if linkedin_presence:
        linkedin_criteria = [
            {
                "name": "Public link present",
                "score": 3,
                "weight": 3,
                "insight": "LinkedIn profile link found in resume."
            }
        ]
        linkedin_score = sum(c["score"] for c in linkedin_criteria)
    else:
        linkedin_criteria = [
            {
                "name": "Public link present",
                "score": 0,
                "weight": 3,
                "insight": "No LinkedIn link found. Add it to boost visibility."
            }
        ]
        linkedin_score = 0
        suggestions.append("Suggestion: Add a public LinkedIn link to enhance recruiter visibility.")

    sections["LinkedIn"] = {
        "score": linkedin_score,
        "weight": 3,
        "grade": get_grade_tag(linkedin_score),
        "sub_criteria": linkedin_criteria
    }

    # 5. Resume (ATS Score)
    resume_criteria = []
    resume_section_score = random.randint(50, 100) # Placeholder score
    resume_criteria = [
        {'name': 'ATS-friendly layout', 'score': 3, 'weight': 3, 'insight': 'Uses readable fonts, minimal columns, no images.'},
        {'name': 'Action verbs & quantified results', 'score': 4, 'weight': 4, 'insight': '“Reduced X by Y%” > “Responsible for X”'},
        {'name': 'Job-relevant keyword alignment', 'score': 3, 'weight': 3, 'insight': 'Matches keywords from job descriptions.'},
        {'name': 'Brevity and conciseness', 'score': 2, 'weight': 2, 'insight': 'Ideal resumes stay under 2 pages.'},
        {'name': 'Minimal jargon / repetition', 'score': 3, 'weight': 3, 'insight': 'Recruiters prefer clarity.'}
    ]
    sections['Resume (ATS Score)'] = {'score': resume_section_score, 'grade': get_grade_tag(resume_section_score), 'weight': TECHNICAL_WEIGHTS['Resume (ATS Score)'], 'sub_criteria': resume_criteria}
    
    # 6. Certifications & Branding
    cert_criteria = []
    cert_section_score = 0
    if cert_presence:
        cert_section_score = 65
        cert_criteria = [
            {'name': 'Role-relevant certifications', 'score': 5, 'weight': 5, 'insight': 'From platforms like LinkedIn Learning, Coursera, etc.'},
            {'name': 'Credibility of platform', 'score': 5, 'weight': 5, 'insight': 'Higher points for well-known issuers.'},
            {'name': 'Recency (within last 2 years)', 'score': 3, 'weight': 3, 'insight': 'Recent certifications are weighted higher.'},
            {'name': 'Completeness (title + issuer)', 'score': 2, 'weight': 2, 'insight': 'No “Free Audit Available” tags; proper naming only.'}
        ]
    else:
        cert_section_score = 0
        cert_suggestions = get_cert_suggestions(domain)
        suggestions.append("Suggestion: Obtain role-relevant certifications to stand out.")
        cert_criteria = [{'name': 'Certifications present', 'score': 0, 'weight': 15, 'insight': 'No certifications were detected in your resume.'}]
    
    sections['Certifications & Branding'] = {'score': cert_section_score, 'grade': get_grade_tag(cert_section_score), 'weight': TECHNICAL_WEIGHTS['Certifications & Branding'], 'sub_criteria': cert_criteria, 'recommendations': cert_suggestions if not cert_presence else []}
    
    # Calculate overall score average
    all_section_scores = [s['score'] for s in sections.values()]
    overall_score_average = sum(all_section_scores) / len(all_section_scores)

    # Final Grade Interpretation
    overall_grade = get_grade_tag(overall_score_average)

    return {
        "sections": sections,
        "overall_score_average": int(overall_score_average),
        "overall_grade": overall_grade,
        "suggestions": suggestions
    }

# --- Plotting functions (no change needed for library version) ---
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import io
import base64
from .utils import get_grade_tag # Import from local utils for consistency

def prepare_chart_data(score_breakdown):
    """
    Prepares a dictionary of data that can be used directly by Chart.js.
    """
    labels = list(score_breakdown.keys())
    scores = [data['score'] for data in score_breakdown.values()]
    
    chart_colors = []
    for data in score_breakdown.values():
        grade = data['grade'].lower()
        if grade == 'excellent':
            chart_colors.append('#4CAF50')
        elif grade == 'good':
            chart_colors.append('#2196F3')
        elif grade == 'average':
            chart_colors.append('#FF9800')
        else:
            chart_colors.append('#dc3545')
    
    return {
        "labels": labels,
        "scores": scores,
        "backgroundColors": chart_colors,
    }

def generate_pie_chart(sections):
    """
    Generates a pie chart from section scores and returns it as a base64-encoded image.
    """
    labels = list(sections.keys())
    sizes = [section['score'] for section in sections.values()]
    
    # Map grades to colors for consistency with the report
    colors = []
    for section in sections.values():
        grade = section['grade'].lower()
        if grade == 'excellent':
            colors.append('#4CAF50')
        elif grade == 'good':
            colors.append('#2196F3')
        elif grade == 'average':
            colors.append('#FF9800')
        else:
            colors.append('#dc3545')

    plt.figure(figsize=(10, 10), facecolor='#121212')
    plt.pie(
        sizes,
        labels=labels,
        autopct='%1.1f%%',
        colors=colors,
        textprops={'color': "w", 'fontsize': 14}
    )
    plt.axis('equal')
    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format='png', facecolor='#121212')
    buf.seek(0)
    encoded = base64.b64encode(buf.read()).decode('utf-8')
    buf.close()
    plt.close()
    return encoded


def generate_pie_chart_v2(sections):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import io, base64

    main_aspects = [
        "Format & Layout",
        "File Type & Parsing",
        "Section Headings & Structure",
        "Job-Title & Core Skills",
        "Dedicated Skills Section"
    ]

    labels = []
    sizes = []
    colors = ['#4CAF50', '#2196F3', '#FF9800', '#dc3545', '#673AB7']

    for aspect in main_aspects:
        if aspect in sections:
            score = sections[aspect].get('score', 0)
            labels.append(aspect)
            sizes.append(score)

    if not sizes or sum(sizes) == 0:
        return None

    fig, ax = plt.subplots(figsize=(10, 10), facecolor='#121212')
    wedges, texts, autotexts = ax.pie(
    sizes,
    autopct='%1.1f%%',
    colors=colors,
    textprops={'color': "white", 'fontsize': 20}
    )
    plt.axis('equal')

    plt.subplots_adjust(bottom=0.25)

    legend_labels = [f"{label}: {size}" for label, size in zip(labels, sizes)]
    ax.legend(
        wedges,
        legend_labels,
        title="Main Aspects",
        loc='lower center',
        bbox_to_anchor=(0.5, -0.5),
        fontsize=20,
        title_fontsize=20,
        frameon=False,
        labelcolor='white'
    )


    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format='png', facecolor='#121212')
    buf.seek(0)
    encoded = base64.b64encode(buf.read()).decode('utf-8')
    buf.close()
    return encoded


# --- Resume ATS Scoring Functions ---
import io
from pdfminer.high_level import extract_text as pdf_extract_text
from docx import Document

def extract_resume_text(file) -> str:
    """
    Accepts InMemoryUploadedFile; returns plain text from PDF/DOCX/TXT.
    """
    name = (file.name or "").lower()
    data = file.read()
    file.seek(0)

    if name.endswith(".pdf"):
        try:
            return pdf_extract_text(io.BytesIO(data))
        except Exception:
            pass
    if name.endswith(".docx"):
        try:
            doc = Document(io.BytesIO(data))
            return "\n".join(p.text for p in doc.paragraphs)
        except Exception:
            pass
    # fallback: try decode as text
    try:
        return data.decode("utf-8", errors="ignore")
    except Exception:
        return ""

def normalize_text(t: str) -> str:
    return re.sub(r"\s+", " ", (t or "")).strip().lower()

def keyword_match_rate(text: str, target_keywords: list[str]) -> float:
    if not target_keywords:
        return 0.0
    t = normalize_text(text)
    hits = sum(1 for kw in target_keywords if kw.lower() in t)
    return hits / max(1, len(target_keywords))

# ===== Resume ATS (15 pts) =====
def ats_resume_scoring(metrics: dict) -> dict:
    """
    Resume (ATS Readiness) breakdown = 15 pts total, plus a normalized score out of 100.
    """
    b = {"items": []}
    total = 0
    MAX_ATS = 15

    # 1) Layout & structure — 3
    pts_layout = int(bool(metrics.get("sections_present"))) \
               + int(bool(metrics.get("single_column"))) \
               + int(bool(metrics.get("text_extractable")))
    b["items"].append({"name": "ATS-friendly layout & structure", "earned": pts_layout, "max": 3})
    total += pts_layout

    # 2) Action verbs & quantified results — 4
    av = float(metrics.get("action_verbs_per_bullet", 0.0))
    qr = float(metrics.get("quantified_bullets_ratio", 0.0))
    pts_actions = (2 if av >= 0.8 else 1 if av >= 0.5 else 0) \
                + (2 if qr >= 0.6 else 1 if qr >= 0.3 else 0)
    b["items"].append({"name": "Action verbs & quantified results", "earned": pts_actions, "max": 4})
    total += pts_actions

    # 3) Keyword alignment — 3
    kmr = float(metrics.get("keyword_match_rate", 0.0))
    pts_keywords = 3 if kmr >= 0.75 else 2 if kmr >= 0.5 else 1 if kmr >= 0.3 else 0
    b["items"].append({"name": "Job-relevant keyword alignment", "earned": pts_keywords, "max": 3})
    total += pts_keywords

    # 4) Brevity & conciseness — 2
    pages = int(metrics.get("pages", 2))
    avg_bullets = float(metrics.get("avg_bullets_per_job", 6.0))
    pts_brev = (1 if pages <= 2 else 0) + (1 if avg_bullets <= 7 else 0)
    b["items"].append({"name": "Brevity & conciseness", "earned": pts_brev, "max": 2})
    total += pts_brev

    # 5) Minimal jargon / repetition — 3
    rep = float(metrics.get("repetition_rate", 0.15))
    jar = float(metrics.get("jargon_rate", 0.2))
    usk = int(metrics.get("unique_skills_count", 8))
    pts_clean = (1 if rep <= 0.10 else 0) + (1 if jar <= 0.15 else 0) + (1 if usk >= 8 else 0)
    b["items"].append({"name": "Minimal jargon / repetition", "earned": pts_clean, "max": 3})
    total += pts_clean

    # Totals and normalized score
    b["subtotal"] = {"earned": total, "max": MAX_ATS}
    b["score_100"] = int(round((total / MAX_ATS) * 100))

    return b

# Role keyword lists (used for metrics + role match for non-tech)
ROLE_KEYWORDS = {
    # Technical
    "software engineer": ["python","java","javascript","react","node","docker","kubernetes","microservices","rest","graphql","aws","gcp","ci/cd","unit testing"],
    "data scientist": ["python","pandas","numpy","sklearn","tensorflow","pytorch","nlp","cv","statistics","sql","experiment","a/b testing","data visualization"],
    "devops engineer": ["ci/cd","docker","kubernetes","terraform","ansible","aws","gcp","azure","monitoring","prometheus","grafana","helm","sre"],
    "web developer": ["html","css","javascript","react","next.js","vue","node","express","rest","graphql","responsive","seo"],
    "mobile app developer": ["android","ios","kotlin","swift","flutter","react native","firebase","push notifications","play store","app store"],
    # Non-technical
    "human resources": ["recruitment","onboarding","payroll","employee engagement","hrms","policy","compliance","talent acquisition","grievance","training"],
    "marketing": ["seo","sem","campaign","content","email marketing","social media","analytics","branding","roi","conversion","google ads"],
    "sales": ["crm","pipeline","lead generation","negotiation","quota","prospecting","closing","upsell","cross-sell","demo"],
    "finance": ["budgeting","forecasting","reconciliation","audit","financial analysis","p&l","variance","sap","tally","excel"],
    "customer service": ["crm","zendesk","freshdesk","sla","csat","ticketing","call handling","escalation","knowledge base","communication"],
}

def derive_resume_metrics(resume_text: str, role_title: str) -> dict:
    t = normalize_text(resume_text)
    sections_present = any(k in t for k in ["experience","work history"]) and ("education" in t) and ("skills" in t)
    single_column = True
    text_extractable = len(t) > 0

    action_verbs = ["led","built","created","designed","implemented","developed","optimized","increased","reduced","launched","migrated","improved","delivered"]
    action_verb_hits = sum(len(re.findall(rf"(^|\n|•|\-)\s*({v})\b", resume_text, flags=re.I)) for v in action_verbs)
    bullets = max(1, len(re.findall(r"(\n•|\n-|\n\d+\.)", resume_text)))
    action_verbs_per_bullet = min(1.0, action_verb_hits / bullets)

    quantified_bullets_ratio = min(1.0, len(re.findall(r"\b\d+(\.\d+)?%?|\b(k|m|bn)\b", resume_text, flags=re.I)) / max(1, bullets))

    pages = max(1, round(len(resume_text) / 2000))
    avg_bullets_per_job = min(12.0, bullets / max(1, len(re.findall(r"\b(company|employer|experience)\b", t))))

    base_role = next((rk for rk in ROLE_KEYWORDS if rk in role_title.lower()), None)
    kws = ROLE_KEYWORDS.get(base_role, [])
    kmr = keyword_match_rate(resume_text, kws) if kws else 0.0

    repetition_rate = 0.08 if "responsible for" not in t else 0.18
    jargon_rate = 0.12 if "synergy" not in t and "leverage" not in t else 0.22

    unique_skills_count = len(set(re.findall(r"[a-zA-Z][a-zA-Z0-9\+\#\.\-]{1,20}", resume_text))) // 50
    unique_skills_count = max(0, min(unique_skills_count, 15))

    return {
        "sections_present": sections_present,
        "single_column": single_column,
        "text_extractable": text_extractable,
        "action_verbs_per_bullet": action_verbs_per_bullet,
        "quantified_bullets_ratio": quantified_bullets_ratio,
        "keyword_match_rate": kmr,
        "pages": pages,
        "avg_bullets_per_job": avg_bullets_per_job,
        "repetition_rate": repetition_rate,
        "jargon_rate": jargon_rate,
        "unique_skills_count": unique_skills_count,
    }