from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django_cryptography.fields import encrypt


class Profile(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        primary_key=True,
    )
    age = models.IntegerField(blank=True, null=True)
    dark_mode = models.BooleanField(default=False)
    profile_picture = models.ImageField(upload_to='media/profile_pictures/', null=True, blank=True)
    coinbase_connected = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user.username} Profile"


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)


# Connect the signal receiver function
post_save.connect(create_user_profile, sender=User)


class EmailList(models.Model):
    email = models.EmailField(unique=True)

    def __str__(self):
        return self.email


class CoinbaseAccount(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='coinbase_account')
    access_token = encrypt(models.CharField(max_length=255))
    refresh_token = encrypt(models.CharField(max_length=255))
    token_type = models.CharField(max_length=40)
    expires_in = models.DateTimeField()
    scope = models.TextField()

    def __str__(self):
        return self.user.username + "'s Coinbase Account"