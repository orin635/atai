from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver


class Profile(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        primary_key=True,
    )
    age = models.IntegerField(blank=True, null=True)
    dark_mode = models.BooleanField(default=False)
    profile_picture = models.ImageField(upload_to='media/profile_pictures/', null=True, blank=True)

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
