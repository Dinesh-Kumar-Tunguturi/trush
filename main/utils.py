import re, io, base64, requests, os
import docx2txt
import fitz  # PyMuPDF
from docx import Document
import matplotlib.pyplot as plt
from textstat import flesch_reading_ease

# Gemini API
import google.generativeai as genai
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")  # put in .env
genai.configure(api_key=GEMINI_API_KEY)


# ----------------------------
# Resume Text Extraction
# ----------------------------
def extract_resume_text(file):
    if file.name.endswith(".docx"):
        return docx2txt.process(file)
    elif file.name.endswith(".pdf"):
        text = ""
        with fitz.open(stream=file.read(), filetype="pdf") as doc:
            for page in doc:
                text += page.get_text("text")
        return text
    return ""


# ----------------------------
# Hyperlink Extraction
# ----------------------------
def extract_hyperlinks_docx(file_path):
    doc = Document(file_path)
    links = []
    for rel in doc.part.rels.values():
        if "hyperlink" in rel.reltype:
            links.append(rel.target_ref)
    return links

def extract_hyperlinks_pdf(file):
    links = []
    with fitz.open(stream=file.read(), filetype="pdf") as doc:
        for page in doc:
            for link in page.get_links():
                if "uri" in link:
                    links.append(link["uri"])
    return links

def extract_and_identify_links(text):
    urls = re.findall(r"(https?://\S+)", text)
    identified = {"linkedin": None, "github": None, "portfolio": []}
    for url in urls:
        if "linkedin" in url:
            identified["linkedin"] = url
        elif "github" in url:
            identified["github"] = url
        else:
            identified["portfolio"].append(url)
    return identified


# ----------------------------
# GitHub API Stats
# ----------------------------
def fetch_github_stats(username):
    """Fetch GitHub stats using public API"""
    try:
        url = f"https://api.github.com/users/{username}/repos"
        r = requests.get(url, headers={"Accept": "application/vnd.github+json"})
        if r.status_code != 200:
            return {"repos": 0, "stars": 0, "followers": 0}

        repos = r.json()
        stars = sum(repo.get("stargazers_count", 0) for repo in repos)
        return {
            "repos": len(repos),
            "stars": stars,
            "followers": requests.get(
                f"https://api.github.com/users/{username}"
            ).json().get("followers", 0),
        }
    except Exception:
        return {"repos": 0, "stars": 0, "followers": 0}


# ----------------------------
# ATS Analysis via Gemini
# ----------------------------
def gemini_resume_analysis(text, role_title):
    """Ask Gemini to analyze the resume ATS-style"""
    prompt = f"""
    You are an ATS evaluator. Analyze this resume for the role of {role_title}.
    Provide scores (0-1) for:
    - keyword_density
    - experience_match
    - skills_match
    - education_match
    Also give a short justification.
    
    Resume Text:
    {text[:5000]}  # truncated to avoid token overload
    """

    try:
        model = genai.GenerativeModel("gemini-pro")
        response = model.generate_content(prompt)
        raw = response.text

        # Simple regex-based extraction
        scores = {
            "keyword_density": float(re.search(r"keyword_density[:\- ]+([0-9\.]+)", raw).group(1)) if re.search(r"keyword_density[:\- ]+([0-9\.]+)", raw) else 0.5,
            "experience_match": float(re.search(r"experience_match[:\- ]+([0-9\.]+)", raw).group(1)) if re.search(r"experience_match[:\- ]+([0-9\.]+)", raw) else 0.5,
            "skills_match": float(re.search(r"skills_match[:\- ]+([0-9\.]+)", raw).group(1)) if re.search(r"skills_match[:\- ]+([0-9\.]+)", raw) else 0.5,
            "education_match": float(re.search(r"education_match[:\- ]+([0-9\.]+)", raw).group(1)) if re.search(r"education_match[:\- ]+([0-9\.]+)", raw) else 0.5,
        }
        scores["readability"] = flesch_reading_ease(text) if text else 0
        return scores, raw
    except Exception as e:
        return {
            "keyword_density": 0.5,
            "experience_match": 0.5,
            "skills_match": 0.5,
            "education_match": 0.5,
            "readability": flesch_reading_ease(text) if text else 0,
        }, f"Error: {e}"


def ats_resume_scoring(metrics):
    weights = {
        "keyword_density": 0.25,
        "experience_match": 0.25,
        "skills_match": 0.2,
        "education_match": 0.15,
        "readability": 0.15
    }
    score = sum(metrics.get(k, 0) * w for k, w in weights.items())
    return {"ats_score": round(score * 100, 2), "details": metrics}


# ----------------------------
# Dynamic ATS + Profiles
# ----------------------------
def calculate_dynamic_ats_score(text, role_title, github_username, links):
    sections = {}

    # Gemini ATS analysis
    metrics, gemini_raw = gemini_resume_analysis(text, role_title)
    ats_report = ats_resume_scoring(metrics)
    sections["ATS Match"] = ats_report["ats_score"]

    # LinkedIn
    sections["LinkedIn"] = 90 if links.get("linkedin") else 40

    # GitHub
    if github_username:
        gh_stats = fetch_github_stats(github_username)
        gh_score = min(100, 40 + gh_stats["repos"] * 2 + gh_stats["stars"] * 0.5 + gh_stats["followers"])
        sections["GitHub"] = gh_score
    else:
        sections["GitHub"] = 30

    # Portfolio
    sections["Portfolio"] = 70 if links.get("portfolio") else 30

    # Final
    overall_score = sum(sections.values()) / len(sections)
    grade = "A+" if overall_score > 85 else "A" if overall_score > 70 else "B"

    return {
        "sections": sections,
        "overall_score_average": round(overall_score, 2),
        "overall_grade": grade,
        "ats_report": ats_report,
        "gemini_feedback": gemini_raw,
        "suggestions": suggest_improvements(sections),
    }


def suggest_improvements(sections):
    suggestions = []
    if sections.get("LinkedIn", 0) < 60:
        suggestions.append("Add a strong LinkedIn profile link.")
    if sections.get("GitHub", 0) < 60:
        suggestions.append("Include GitHub with active projects.")
    if sections.get("Portfolio", 0) < 60:
        suggestions.append("Showcase personal portfolio or website.")
    return suggestions


# ----------------------------
# Charts
# ----------------------------
def generate_pie_chart(sections):
    labels = list(sections.keys())
    sizes = list(sections.values())
    fig, ax = plt.subplots()
    ax.pie(sizes, labels=labels, autopct="%1.1f%%", startangle=90)
    ax.axis("equal")
    buf = io.BytesIO()
    plt.savefig(buf, format="png")
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("utf-8")
