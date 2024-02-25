# create_profiles.py

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from atai_app.models import Profile  # Import your Profile model


class Command(BaseCommand):
    help = 'Creates profiles for existing users'

    def handle(self, *args, **kwargs):
        existing_users = User.objects.all()
        for user in existing_users:
            # Check if a profile already exists for the user
            if not hasattr(user, 'profile'):
                Profile.objects.create(user=user)
                self.stdout.write(self.style.SUCCESS(f'Profile created for {user.username}'))
            else:
                self.stdout.write(self.style.WARNING(f'A profile already exists for {user.username}'))
