from django.urls import path
from main import views
from main import auth_views, payment_views, score_utils

urlpatterns = [
    # Basic Views
    path('', views.landing, name='landing'),
    path('signin/', views.signin, name='signin'),
    path('login/', views.login_view, name='login'),
    path('signup/', views.signup, name='signup'),
    path('about_us/', views.about_us, name='about_us'),

    # OTP Views
    path('send-otp/', views.send_otp, name='send_otp'),
    path('verify-otp/', views.verify_otp, name='verify_otp'),
    path('send-signup-otp/', views.send_signup_otp, name='send_signup_otp'),
    path('verify-signup-otp/', views.verify_signup_otp, name='verify_signup_otp'),

    # Resume Analyzer Views
    path('upload_resume/', views.upload_resume, name='upload_resume'),
    path('analyze_resume/', views.analyze_resume, name='analyze_resume'),
    path('analyze_resume/', views.analyze_resume, name='analyze_resume'),
    path('analyze_resume_v2/', views.analyze_resume_v2, name='analyze_resume_v2'),

    # Profile Building & Payment Views
    path('profile_building/', views.profile_building, name='profile_building'),
    # This is the corrected URL pattern
    path('payment_instructions/<int:plan_id>/', views.payment_instructions, name='payment_instructions'),
    path('submit_payment_details/', views.submit_payment_details, name='submit_payment_details'),
    path('payment_submission_success/', views.payment_submission_success, name='payment_submission_success'),
]