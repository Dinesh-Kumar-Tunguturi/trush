from django import forms

class PaymentDetailsForm(forms.Form):
    name = forms.CharField(max_length=255, label="Your Name")
    utr_number = forms.CharField(max_length=50, label="UTR / Transaction ID")
    transaction_screenshot = forms.FileField(label="Upload Transaction Screenshot")
    resume = forms.FileField(label="Upload Your Resume")
    plan_id = forms.IntegerField(widget=forms.HiddenInput(), required=False) 