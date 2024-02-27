"""
URL configuration for atai_project project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from django.views.generic import TemplateView
from atai_app.views import logout_user, register, dashboard, trade_settings, live_charts, error_redirect, coinbase_login, coinbase_callback
from django.conf.urls.static import static
from django.conf import settings


urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('django.contrib.auth.urls')),
    path("", dashboard, name="dashboard"),
    path("logout_user", logout_user, name="logout_user"),
    path("register/", register, name="register"),
    path("trade_settings", trade_settings, name="trade_settings"),
    path("live_charts", live_charts, name="live_charts"),
    path('error_redirect', error_redirect, name='error_redirect'),
    path('coinbase/login/', coinbase_login, name='coinbase_login'),
    path('coinbase/callback/', coinbase_callback, name='coinbase_callback'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
