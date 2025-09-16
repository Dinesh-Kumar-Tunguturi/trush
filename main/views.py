# app/views.py

from __future__ import annotations

import os
import re
import io
import base64
import random
import tempfile
import hashlib
import json
from typing import Dict

from django.conf import settings
from django.core.mail import send_mail
from django.shortcuts import render, redirect
from django.template.loader import get_template
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.http import JsonResponse, HttpResponse, HttpResponseBadRequest
from dotenv import load_dotenv

load_dotenv()

# PDF export
from xhtml2pdf import pisa

# Matplotlib for pie charts
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# Utils & scoring
from .utils import (
    extract_applicant_name,
    extract_github_username,
    extract_leetcode_username,
    calculate_dynamic_ats_score,
    derive_resume_metrics,
    ats_resume_scoring,
    extract_links_combined,
    extract_text_from_docx,
    generate_pie_chart_v2,
)

from .ats_score_non_tech import ats_scoring_non_tech_v2
from .services.certifications import suggest_role_certifications
from .forms import PaymentDetailsForm

# Twilio (use environment/setting variables)
# from twilio.rest import Client
# twilio_account_sid = os.getenv('TWILIO_ACCOUNT_SID')
# twilio_auth_token = os.getenv('TWILIO_AUTH_TOKEN')
# if twilio_account_sid and twilio_auth_token:
#     twilio_client = Client(twilio_account_sid, twilio_auth_token)

# ========= In-memory OTP / user stores (for demo, replace with DB in prod) =========
registered_users: Dict[str, str] = {}
OTP_TTL_SECONDS = 300  # 5 min

def norm_email(email: str) -> str:
    return (email or "").strip().lower()

def norm_mobile(mobile: str) -> str:
    return re.sub(r"\D+", "", (mobile or "").strip())

def send_otp_email(to_email: str, otp: str, subject: str):
    send_mail(
        subject=subject,
        message=f"Your OTP is {otp}. It will expire in {OTP_TTL_SECONDS // 60} minutes.",
        from_email=os.getenv("DEFAULT_FROM_EMAIL"),
        recipient_list=[to_email],
        fail_silently=False,
    )

# ========= Basic pages =========
def landing(request): return render(request, "landing.html")
def signin(request): return render(request, "login.html")
def login_view(request): return render(request, "login.html")
def signup(request): return render(request, "login.html")
def about_us(request): return render(request, "about_us.html")
def upload_resume(request): return render(request, "upload_resume.html")
def profile_building(request): return render(request, "subscription_plans.html")
def payment_submission_success(request): return render(request, "payment_submission_success.html")

# ========= OTP SIGNUP / LOGIN =========
@csrf_exempt
def send_signup_otp(request):
    if request.method != "POST":
        return JsonResponse({"status": "error", "message": "Invalid request"}, status=405)
    email = norm_email(request.POST.get("email", ""))
    mobile = norm_mobile(request.POST.get("mobile", ""))
    if not email or not mobile:
        return JsonResponse({"status": "error", "message": "Email and mobile required"}, status=400)
    otp = f"{random.randint(100000, 999999)}"
    cache_key = f"signup_otp:{email}:{mobile}"
    from django.core.cache import cache
    cache.set(cache_key, otp, timeout=OTP_TTL_SECONDS)
    try:
        send_otp_email(email, otp, subject="Your ApplyWizz Signup OTP")
        return JsonResponse({"status": "success", "message": "OTP sent to your email"})
    except Exception as e:
        return JsonResponse({"status": "error", "message": f"Failed to send OTP: {e}"}, status=500)

@csrf_exempt
def verify_signup_otp(request):
    if request.method != "POST":
        return JsonResponse({"status": "error", "message": "Invalid request"}, status=405)
    email = norm_email(request.POST.get("email", ""))
    mobile = norm_mobile(request.POST.get("mobile", ""))
    otp = (request.POST.get("otp", "") or "").strip()
    from django.core.cache import cache
    cache_key = f"signup_otp:{email}:{mobile}"
    stored_otp = cache.get(cache_key)
    if stored_otp and stored_otp == otp:
        registered_users[mobile] = email
        cache.delete(cache_key)
        return JsonResponse({"status": "success", "redirect_url": "/login"})
    else:
        return JsonResponse({"status": "error", "message": "Invalid or expired OTP"}, status=400)

@csrf_exempt
def send_login_otp(request):
    if request.method != "POST":
        return JsonResponse({"status": "error", "message": "Invalid request"}, status=405)
    email = norm_email(request.POST.get("email", ""))
    if not email:
        return JsonResponse({"status": "error", "message": "Email required"}, status=400)
    otp = f"{random.randint(100000, 999999)}"
    from django.core.cache import cache
    cache_key = f"login_otp:{email}"
    cache.set(cache_key, otp, timeout=OTP_TTL_SECONDS)
    try:
        send_otp_email(email, otp, subject="Your ApplyWizz Login OTP")
        return JsonResponse({"status": "success", "message": "OTP sent to your email"})
    except Exception as e:
        return JsonResponse({"status": "error", "message": f"Failed to send OTP: {e}"}, status=500)

@csrf_exempt
def verify_login_otp(request):
    if request.method != "POST":
        return JsonResponse({"status": "error", "message": "Invalid request"}, status=405)
    email = norm_email(request.POST.get("email", ""))
    otp = (request.POST.get("otp", "") or "").strip()
    from django.core.cache import cache
    cache_key = f"login_otp:{email}"
    stored_otp = cache.get(cache_key)
    if stored_otp and stored_otp == otp:
        cache.delete(cache_key)
        return JsonResponse({"status": "success", "redirect_url": "/upload_resume"})
    else:
        return JsonResponse({"status": "error", "message": "Invalid or expired OTP"}, status=400)

# ========= PDF Download =========
def download_resume_pdf(request):
    context = request.session.get("resume_context", {})
    template_path = "resume_result.html"
    if context and context.get("github_detection") == "NO" and context.get("role") in ["Human Resources", "Marketing", "Sales", "Finance", "Customer Service"]:
        template_path = "score_of_non_tech.html"
    template = get_template(template_path)
    html = template.render(context)
    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = 'attachment; filename="resume_report.pdf"'
    pisa_status = pisa.CreatePDF(html, dest=response)
    if pisa_status.err:
        return HttpResponse("We had some errors <pre>" + html + "</pre>")
    return response

# ========= Pie Chart =========
def generate_pie_chart_tech(sections: Dict) -> str | None:
    labels, sizes = [], []
    for label, data in (sections or {}).items():
        score = data.get("score", 0)
        if isinstance(score, (int, float)) and score == score:
            labels.append(label)
            sizes.append(float(score))
    if not sizes or sum(sizes) == 0: return None
    fig, ax = plt.subplots(figsize=(8, 8), facecolor="#121212")
    wedges = ax.pie(sizes, labels=None)[0]
    ax.legend(wedges, labels, loc="lower center", bbox_to_anchor=(0.5, -0.15), fontsize=18, frameon=False, labelcolor="white", ncol=2, title="Categories", title_fontsize=13)
    ax.set_facecolor("#121212")
    plt.axis("equal")
    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format="png", facecolor="#121212")
    buf.seek(0)
    encoded = base64.b64encode(buf.read()).decode("utf-8")
    buf.close()
    plt.close(fig)
    return encoded

# ========= Result key helper =========
def _make_result_key(role_type: str, role_slug: str, resume_text: str, github_username: str = "", leetcode_username: str = "") -> str:
    payload = json.dumps({
        "role_type": role_type,
        "role_slug": role_slug,
        "resume_hash": hashlib.sha256((resume_text or "").encode("utf-8")).hexdigest(),
        "github": github_username or "",
        "leetcode": leetcode_username or "",
    }, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()

# ========= Technical resume analysis =========
@require_POST
def analyze_resume(request):
    if request.POST.get("domain") != "technical": return HttpResponseBadRequest("Please choose Technical category.")
    if "resume" not in request.FILES: return HttpResponseBadRequest("Resume file required.")
    
    resume_file = request.FILES["resume"]
    ext = os.path.splitext(resume_file.name)[1].lower()
    
    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
        for chunk in resume_file.chunks(): tmp.write(chunk)
        temp_path = tmp.name

    if ext == ".pdf":
        extracted_links, resume_text = extract_links_combined(temp_path)
    elif ext == ".docx":
        resume_text = extract_text_from_docx(temp_path)
        extracted_links = []
    else:
        os.unlink(temp_path)
        return HttpResponseBadRequest("Unsupported file format.")

    try:
        applicant_name = extract_applicant_name(resume_text) or "Candidate"
        github_username = request.POST.get("github_username", "").strip() or extract_github_username(resume_text) or ""
        leetcode_username = request.POST.get("leetcode_username", "").strip() or extract_leetcode_username(resume_text) or ""
        role_slug = request.POST.get("tech_role", "software_engineer")
        TECH_ROLE_MAP = {"software_engineer":"Software Engineer","data_scientist":"Data Scientist","devops_engineer":"DevOps Engineer","web_developer":"Web Developer","mobile_developer":"Mobile App Developer"}
        role_title = TECH_ROLE_MAP.get(role_slug,"Software Engineer")
        
        metrics = derive_resume_metrics(resume_text, role_title)
        ats_resume_score_dict = ats_resume_scoring(metrics)
        raw_100 = ats_resume_score_dict.get("score_100") or round((ats_resume_score_dict.get("subtotal", {}).get("earned",0)/ats_resume_score_dict.get("subtotal", {}).get("max",15))*100)
        ats_resume_score = max(60, int(raw_100))

        ats_result = calculate_dynamic_ats_score(resume_text, github_username, leetcode_username, extracted_links)
        sections = ats_result.get("sections", {})
        original_ats_section = sections.get("Resume (ATS Score)", {})
        
        sections["Resume (ATS Score)"] = {
            "score": ats_resume_score,
            "grade": original_ats_section.get("grade",""),
            "sub_criteria": original_ats_section.get("sub_criteria", ats_resume_score_dict.get("items", []))
        }

        desired_order = ["Resume (ATS Score)","GitHub Profile","Portfolio Website","LeetCode/DSA Skills","LinkedIn","Certifications & Branding"]
        score_breakdown_ordered = [(k, sections[k]) for k in desired_order if k in sections]
        for k,v in sections.items(): 
            if k not in desired_order: score_breakdown_ordered.append((k,v))
            
        pie_chart_image = generate_pie_chart_tech(sections)
        overall_score_average = int(ats_result.get("overall_score_average",0))
        suggestions = (ats_result.get("suggestions") or [])[:2]
        recommended_certs = suggest_role_certifications(role_title)
        
        context = {
            "result_key": _make_result_key("technical", role_slug, resume_text, github_username, leetcode_username),
            "applicant_name": applicant_name,
            "contact_detection": "YES" if any(s in resume_text.lower() for s in ["@", "phone", "email"]) else "NO",
            "linkedin_detection": "YES" if "linkedin.com" in resume_text.lower() else "NO",
            "github_detection": "YES" if ("github.com" in resume_text.lower() or github_username) else "NO",
            "ats_score": ats_resume_score,
            "overall_score_average": overall_score_average,
            "overall_grade": ats_result.get("overall_grade",""),
            "score_breakdown": sections,
            "score_breakdown_ordered": score_breakdown_ordered,
            "pie_chart_image": pie_chart_image,
            "missing_certifications": recommended_certs,
            "suggestions": suggestions,
            "role": role_title,
        }
        
        request.session["resume_context_tech"] = context
        request.session.modified = True
        return redirect("show_report_technical")
    finally:
        os.unlink(temp_path)

# ========= Non-technical resume analysis =========
@require_POST
def analyze_resume_v2(request):
    context = {
        "applicant_name":"N/A","ats_score":0,"overall_score_average":0,"overall_grade":"N/A","score_breakdown":{},
        "suggestions":[],"pie_chart_image":None,"detected_links":[],"error":None,
        "contact_detection":"NO","github_detection":"NO","linkedin_detection":"NO",
    }
    
    if request.method == 'POST' and request.FILES.get('resume'):
        resume_file = request.FILES['resume']
        ext = os.path.splitext(resume_file.name)[1].lower()

        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            for chunk in resume_file.chunks(): tmp.write(chunk)
            temp_path = tmp.name

        try:
            if ext == ".pdf":
                extracted_links, resume_text = extract_links_combined(temp_path)
            elif ext == ".docx":
                resume_text = extract_text_from_docx(temp_path)
                extracted_links = []
            else:
                context["error"] = "Unsupported file format."
                return render(request, 'score_of_non_tech.html', context)
            
            text_lower = resume_text.lower()
            contact_detection = "YES" if any(x in text_lower for x in ["@", "phone", "email"]) else "NO"
            github_detection = "YES" if ("github.com" in text_lower or any("github.com" in link for link in extracted_links)) else "NO"
            linkedin_detection = "YES" if ("linkedin.com" in text_lower or any("linkedin.com" in link for link in extracted_links)) else "NO"
            applicant_name = extract_applicant_name(resume_text) or "N/A"
            role_title = request.POST.get("role_title","human resources")

            # Updated function call
            ats_result = ats_scoring_non_tech_v2(temp_path)

            context.update({
                "applicant_name": applicant_name,
                "ats_score": ats_result.get("ats_score", 0),
                "overall_score_average": ats_result.get("overall_score_average", 0),
                "overall_grade": ats_result.get("overall_grade", "N/A"),
                "score_breakdown": ats_result.get("score_breakdown", {}),
                "pie_chart_image": ats_result.get("pie_chart_image"),
                "suggestions": ats_result.get("suggestions", []),
                "detected_links": extracted_links,
                "contact_detection": contact_detection,
                "github_detection": github_detection,
                "linkedin_detection": linkedin_detection,
            })
        finally:
            os.unlink(temp_path)

    request.session["resume_context_nontech"] = context
    request.session.modified = True
    return render(request,'score_of_non_tech.html',context)

# ========= Show reports =========
def show_report_technical(request):
    ctx = request.session.get("resume_context_tech")
    if not ctx: return redirect("upload_page")
    return render(request,"resume_result.html",ctx)

def show_report_nontechnical(request):
    ctx = request.session.get("resume_context_nontech")
    if not ctx: return redirect("upload_page")
    return render(request,"score_of_non_tech.html",ctx)

def why(request):
    return render(request,"why.html")

def who(request):

    return render(request,"who.html")
