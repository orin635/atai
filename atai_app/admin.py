from django.contrib import admin

from .models import Profile, EmailList, CoinbaseAccount

admin.site.register(Profile)
admin.site.register(EmailList)
admin.site.register(CoinbaseAccount)