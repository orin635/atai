from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import render, redirect, reverse
from django.contrib.auth import logout
from .forms import EmailForm, ProfileForm
from .models import EmailList, CoinbaseAccount, Profile, Trade
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.utils import timezone
from django.core.cache import cache
import datetime
import requests
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
import json
from django.core.serializers import serialize


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


def get_coinbase_prices(currencies, base_currency='EUR'):
    prices = {}
    for currency in currencies:
        # Coinbase API endpoint for current exchange rates for a currency
        api_url = f'https://api.coinbase.com/v2/exchange-rates?currency={currency}'

        try:
            response = requests.get(api_url)
            response.raise_for_status()  # Check for HTTP errors
            data = response.json()

            # Get the exchange rate from the specified currency to the base currency (e.g., 'EUR')
            rate = data['data']['rates'][base_currency]
            prices[currency] = rate
        except requests.RequestException as e:
            print(f"An error occurred while fetching prices for {currency}: {e}")
        except KeyError:
            print(f"Could not find rate for {currency} in response.")

    return prices


def dashboard(request):
    if not request.user.is_authenticated:  # If user is not logged in, redirect to login page
        return redirect('/accounts/login')
    else:
        cache_key_account = f'{request.user.id}_coinbase_account'
        accounts = cache.get(cache_key_account)

        if accounts is not None:
            print("loaded from cache")
            return render(request, 'dashboard.html', {
                'accounts': accounts
            })

        else:
            try:
                # Retrieve the CoinbaseAccount for the current user
                coinbase_account = CoinbaseAccount.objects.get(user=request.user)
            except CoinbaseAccount.DoesNotExist:
                return render(request, 'dashboard.html', {
                    'account_name': "NA",
                    'eth_balance': "NA"
                })

            if timezone.now() >= coinbase_account.expires_in:
                # if token has expired use the refresh token to get a new access token
                refresh_url = 'https://api.coinbase.com/oauth/token'
                refresh_data = {
                    'grant_type': 'refresh_token',
                    'refresh_token': coinbase_account.refresh_token,
                    'client_id': settings.COINBASE_CLIENT_ID,
                    'client_secret': settings.COINBASE_CLIENT_SECRET,
                }
                response = requests.post(refresh_url, data=refresh_data)
                if response.status_code == 200:
                    token_info = response.json()
                    expires_in = timezone.now() + timezone.timedelta(seconds=token_info['expires_in'])
                    # Update the CoinbaseAccount with the new access and refresh tokens
                    CoinbaseAccount.objects.filter(user=request.user).update(
                        access_token=token_info['access_token'],
                        refresh_token=token_info['refresh_token'],
                        expires_in=expires_in
                    )
                    access_token = token_info['access_token']
                else:
                    return redirect('/error/')

            else:
                access_token = coinbase_account.access_token

            if access_token:
                # get user profile information
                user_info_url = "https://api.coinbase.com/v2/accounts/?limit=100"
                response = requests.get(user_info_url, headers={'Authorization': f'Bearer {access_token}',
                                                                'CB-VERSION': 'YYYY-MM-DD'})

                if response.status_code == 200:
                    accounts_data = response.json()['data']

                    coin_codes = {account['currency']['code'] for account in accounts_data if
                                  float(account['balance']['amount']) > 0.00001}

                    current_prices = get_coinbase_prices(coin_codes)
                    accounts_list = [{
                        'name': account['name'],
                        'balance_amount': float(account['balance']['amount']),
                        'balance_currency': account['balance']['currency'],
                        'currency_code': account['currency']['code'],
                        'currency_name': account['currency']['name'],
                        'currency_color': account['currency']['color'],
                        'current_price': float(current_prices.get(account['currency']['code'])),
                        'balance_value': float(account['balance']['amount']) * float(
                            current_prices.get(account['currency']['code'])),
                    } for account in accounts_data if float(account['balance']['amount']) > 0.00001 and (
                                float(account['balance']['amount']) * float(
                            current_prices.get(account['currency']['code'])) > 1)]

                    accounts_list = sorted(accounts_list, key=lambda x: x['balance_value'], reverse=True)

                    # Cache and render
                    cache.set(cache_key_account, accounts_list, timeout=900)
                    return render(request, 'dashboard.html', {'accounts': accounts_list})

            return redirect('/error_redirect')


@login_required
def trade_settings(request):
    try:
        profile = request.user.profile
    except Profile.DoesNotExist:
        profile = None

    if request.method == 'POST':
        form = ProfileForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            return redirect('/trade_settings')
    else:
        form = ProfileForm(instance=profile)

    # Calculate total profit/loss from completed trades
    total_profit_loss = Trade.objects.filter(profile=profile, is_active=False).aggregate(
        total=Sum('profit_loss'))['total'] or 0

    # List all trades
    trades = Trade.objects.filter(profile=profile).order_by('-is_active')

    context = {
        'form': form,
        'total_profit_loss': total_profit_loss,
        'trades': trades,
    }

    return render(request, 'tradesettings.html', context)


def live_charts(request):
    return render(request, 'livecharts.html')


def profile(request):
    return render(request, 'profile.html')


def error_redirect(request):
    return render(request, 'error.html')


def coinbase_login(request):
    # Coinbase OAuth2 URL
    parameters = {
        'response_type': 'code',
        'client_id': settings.COINBASE_CLIENT_ID,
        'redirect_uri': settings.COINBASE_REDIRECT_URI,
        'scope': 'wallet:accounts:read,wallet:orders:create,wallet:orders:read,wallet:buys:create,'
                 'wallet:sells:create,wallet:notifications:read,wallet:buys:read,wallet:sells:read,'
                 'wallet:transactions:read,wallet:user:read',
    }
    url = (f"https://www.coinbase.com/oauth/authorize?response_type={parameters['response_type']}"
           f"&client_id={parameters['client_id']}&redirect_uri={parameters['redirect_uri']}"
           f"&scope={parameters['scope']}")
    return redirect(url)


def coinbase_callback(request):
    error = request.GET.get('error')
    if error:
        # Handle an error
        return redirect('/error')

    authorization_code = request.GET.get('code')
    if authorization_code:
        # Exchange the authorization code for an access token
        token_url = 'https://api.coinbase.com/oauth/token'
        redirect_uri = settings.COINBASE_REDIRECT_URI
        data = {
            'grant_type': 'authorization_code',
            'code': authorization_code,
            'redirect_uri': redirect_uri,
            'client_id': settings.COINBASE_CLIENT_ID,
            'client_secret': settings.COINBASE_CLIENT_SECRET,
        }
        response = requests.post(token_url, data=data)
        if response.status_code == 200:
            token_info = response.json()
            expires_in = timezone.now() + datetime.timedelta(seconds=token_info['expires_in'])
            # Check if the user is authenticated before linking Coinbase account
            if request.user.is_authenticated:
                CoinbaseAccount.objects.update_or_create(
                    user=request.user,
                    defaults={
                        'access_token': token_info['access_token'],
                        'refresh_token': token_info['refresh_token'],
                        'token_type': token_info['token_type'],
                        'expires_in': expires_in,
                        'scope': token_info['scope'],
                    },
                )

                # Update users Profile to set coinbase_connected to True
                Profile.objects.update_or_create(
                    user=request.user,
                    defaults={'coinbase_connected': True},
                )

                return redirect('/')
            else:
                # If user is not authenticated
                return redirect('/accounts/login/')
        else:
            # If error in token exchange
            return redirect('/error_redirect')
    else:
        # If code was provided
        return redirect('/error_redirect')


def update_dark_mode(request):
    user_id = request.POST.get('user_id')
    print(user_id)
    dark_mode = request.POST.get('dark_mode') == 'true'
    profile = Profile.objects.get(user__id=user_id)
    profile.dark_mode = dark_mode
    profile.save()
    return JsonResponse({'success': True})
