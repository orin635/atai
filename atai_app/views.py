from django.shortcuts import render, redirect, reverse
from django.contrib.auth import logout
from .forms import EmailForm
from .models import EmailList


def logout_user(request):
    logout(request)
    return redirect(reverse('login'))


def register(request):
    if request.method == 'POST':
        form = EmailForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            existing_email = EmailList.objects.filter(email=email).exists()
            if not existing_email:
                EmailList.objects.create(email=email)
    else:
        form = EmailForm()
    return render(request, 'register.html', {'form': form})


def dashboard(request):
    print("Received email: {email}", flush=True)
    return render(request, 'dashboard.html')
