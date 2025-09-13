import os
import re
import fitz # PyMuPDF
import docx2txt
import requests
from dotenv import load_dotenv

load_dotenv()

# --- Resume Text Extraction ---
def extract_text_from_pdf(file_path):
    """Extracts text from a PDF file using PyMuPDF (fitz)."""
    text = ""
    try:
        doc = fitz.open(file_path)
        for page in doc:
            text += page.get_text()
    except Exception:
        pass
    return text

def extract_text_from_docx(file_path):
    """Extracts text from a DOCX file using docx2txt."""
    try:
        return docx2txt.process(file_path)
    except Exception:
        return ""

# --- Link Extractors ---
def extract_link(pattern, text):
    """Extracts a single link from text based on a regex pattern."""
    match = re.search(pattern, text)
    return match.group(0) if match else None

# --- Scoring Functions ---
def score_github(github_url):
    """Placeholder for GitHub scoring."""
    return 25 if github_url else 0

def score_leetcode(leetcode_url):
    """Placeholder for LeetCode scoring."""
    return 20 if leetcode_url else 0

def score_portfolio(portfolio_url):
    """Placeholder for Portfolio scoring."""
    return 15 if portfolio_url else 0

def score_linkedin(linkedin_url, resume_text):
    """Placeholder for LinkedIn scoring."""
    return 10 if linkedin_url else 0

def score_resume_structure(text):
    """Placeholder for Resume structure scoring."""
    return 15 if text else 0

def score_certifications(text):
    """Placeholder for Certifications scoring."""
    return 15 if "certificate" in text.lower() else 0

# --- Main Logic ---
def get_overall_score(file_path):
    """
    Calculates an overall ATS score based on file content.
    This function is a simplified, non-Django view version.
    """
    ext = os.path.splitext(file_path)[1].lower()
    if ext == '.pdf':
        text = extract_text_from_pdf(file_path)
    elif ext == '.docx':
        text = extract_text_from_docx(file_path)
    else:
        return {"error": "Unsupported file format."}

    github_url = extract_link(r'https?://github\.com/[A-Za-z0-9_-]+', text)
    leetcode_url = extract_link(r'https?://leetcode\.com/[A-Za-z0-9_-]+', text)
    portfolio_url = extract_link(r'https?://[a-zA-Z0-9.-]+\.(me|tech|dev|xyz|site|vercel\.app|github\.io)', text)
    linkedin_url = extract_link(r'https?://(www\.)?linkedin\.com/in/[A-Za-z0-9_-]+', text)

    scores = {
        "GitHub": score_github(github_url),
        "LeetCode": score_leetcode(leetcode_url),
        "Portfolio": score_portfolio(portfolio_url),
        "LinkedIn": score_linkedin(linkedin_url, text),
        "Resume": score_resume_structure(text),
        "Certifications": score_certifications(text)
    }

    total = sum(scores.values())
    return {"scores": scores, "total": total}