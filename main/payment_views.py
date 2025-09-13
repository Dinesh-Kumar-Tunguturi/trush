import os
from django.shortcuts import render, redirect
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from .forms import PaymentDetailsForm
from .score_utils import verify_bank_transaction

PLANS = {
    1: {"name": "Applywizz Resume", "price": 499, "description": "Builds a resume with the highest ATS score."},
    2: {"name": "Resume + Profile Portfolio", "price": 999, "description": "Includes Resume building and a professional Portfolio Website."},
    3: {"name": "All-in-One Package", "price": 2999, "description": "Includes Resume, Portfolio, and applying to jobs on your behalf."},
}

def profile_building(request):
    """
    Renders the Profile Building page with subscription plans.
    """
    return render(request, 'subscription_plans.html')

def payment_instructions(request, plan_id):
    """
    Displays payment instructions with a QR code for the selected plan.
    """
    plan = PLANS.get(plan_id)
    if not plan:
        return redirect('profile_building')

    qr_code_url = "https://placehold.co/200x200/000000/FFFFFF?text=Scan+to+Pay"
    
    context = {
        'plan': plan,
        'qr_code_url': qr_code_url,
    }
    return render(request, 'payment_instructions.html', context)

def submit_payment_details(request):
    """
    Handles the form for submitting payment details and resume,
    and attempts to verify the transaction.
    """
    plan_id_get = request.GET.get('plan_id')

    if request.method == 'POST':
        form = PaymentDetailsForm(request.POST, request.FILES)
        if form.is_valid():
            name = form.cleaned_data['name']
            utr_number = form.cleaned_data['utr_number']
            transaction_screenshot = form.cleaned_data['transaction_screenshot']
            resume = form.cleaned_data['resume']
            plan_id_post = form.cleaned_data.get('plan_id')
            
            plan = PLANS.get(plan_id_post) if plan_id_post else None
            expected_amount = plan['price'] if plan else 0

            # --- Manual Verification Logic (for a real app) ---
            submission_dir = os.path.join(settings.MEDIA_ROOT, 'submissions', utr_number)
            os.makedirs(submission_dir, exist_ok=True)

            with open(os.path.join(submission_dir, transaction_screenshot.name), 'wb+') as destination:
                for chunk in transaction_screenshot.chunks():
                    destination.write(chunk)
            
            with open(os.path.join(submission_dir, resume.name), 'wb+') as destination:
                for chunk in resume.chunks():
                    destination.write(chunk)
            
            print(f"New submission from {name}:")
            print(f"  - UTR: {utr_number}")
            print(f"  - Plan ID: {plan_id_post}")
            print(f"  - Amount: {expected_amount}")
            print(f"  - Screenshot saved to: {os.path.join(submission_dir, transaction_screenshot.name)}")
            print(f"  - Resume saved to: {os.path.join(submission_dir, resume.name)}")

            return redirect('payment_submission_success')
        else:
            if plan_id_get:
                form = PaymentDetailsForm(request.POST, request.FILES, initial={'plan_id': plan_id_get})
            else:
                form = PaymentDetailsForm(request.POST, request.FILES)

            return render(request, 'payment_form.html', {'form': form})
    else: # GET request
        if plan_id_get:
            form = PaymentDetailsForm(initial={'plan_id': plan_id_get})
        else:
            form = PaymentDetailsForm()
    
    return render(request, 'payment_form.html', {'form': form})

def payment_submission_success(request):
    """
    Renders a success page after the payment details form is submitted.
    """
    return render(request, 'payment_submission_success.html')