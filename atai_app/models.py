from decimal import Decimal

from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django_cryptography.fields import encrypt


class Profile(models.Model):
    RISK_TOLERANCE_CHOICES = [
        (1, 'Low Risk'),
        (2, 'Medium Risk'),
        (3, 'High Risk'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, primary_key=True)
    age = models.IntegerField(blank=True, null=True)
    dark_mode = models.BooleanField(default=False)
    profile_picture = models.ImageField(upload_to='media/profile_pictures/', null=True, blank=True)
    coinbase_connected = models.BooleanField(default=False)
    trade_btc = models.BooleanField(default=False)
    trade_eth = models.BooleanField(default=False)
    trade_quantity = models.IntegerField(default=0, blank=True, null=True)
    risk_tolerance = models.IntegerField(choices=RISK_TOLERANCE_CHOICES, default=1)

    def __str__(self):
        return f"{self.user.username} Profile"


class Trade(models.Model):
    COIN_CHOICES = [
        ('BTC', 'Bitcoin'),
        ('ETH', 'Ethereum'),
    ]

    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name='trades')
    coin_type = models.CharField(max_length=3, choices=COIN_CHOICES)
    is_active = models.BooleanField(default=True)
    buy_price = models.DecimalField(max_digits=10, decimal_places=4)
    sell_price = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    quantity_usdc = models.DecimalField(max_digits=10, decimal_places=2)
    sell_quantity_usdc = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    quantity_coin = models.DecimalField(max_digits=10, decimal_places=8)
    stop_loss = models.DecimalField(max_digits=10, decimal_places=4)
    fee_amount = models.DecimalField(max_digits=10, decimal_places=5)
    take_profit = models.DecimalField(max_digits=10, decimal_places=4)
    profit_loss = models.DecimalField(max_digits=10, decimal_places=4, null=True,
                                      blank=True)

    def __str__(self):
        status = "Active" if self.is_active else "Completed"
        return f"{self.profile.user.username} {status} Trade - {self.coin_type}"

    # Optional: Add a method to calculate profit/loss when a trade is completed
    def calculate_profit_loss(self):
        if self.sell_price and self.buy_price:
            buy_quantity_usdc = Decimal(str(self.quantity_usdc))
            sell_quantity_usdc = Decimal(str(self.sell_quantity_usdc))
            fee_amount = Decimal(str(self.fee_amount))

            # Calculate profit or loss
            self.profit_loss = sell_quantity_usdc - buy_quantity_usdc - fee_amount
            self.save()


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
