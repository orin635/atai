from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import render, redirect, reverse
from django.contrib.auth import logout
from .forms import EmailForm
from .models import EmailList, CoinbaseAccount, Profile
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


def map_currency_codes_to_ids(codes):
    print(codes)
    # Define a unique key for the cache
    cache_key = 'coin_gecko_coin_list'

    # Try to get the cached data
    code_to_id = cache.get(cache_key)

    # If the data is not in the cache, fetch it from CoinGecko
    if not code_to_id:
        url = 'https://api.coingecko.com/api/v3/coins/list'
        try:
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()

            # Create a mapping of symbols to CoinGecko IDs
            code_to_id = {coin['symbol'].upper(): coin['id'] for coin in data}

            # Cache this data for a longer period, for example, 24 hours (86400 seconds)
            cache.set(cache_key, code_to_id, timeout=86400)

        except requests.RequestException as e:
            print(f"An error occurred while mapping codes to IDs: {e}")
            return {}

    # Return a mapping for your specific codes
    return {code: code_to_id.get(code.upper(), '') for code in codes}


def fetch_current_prices(coin_codes):
    # Map codes to CoinGecko IDs
    code_to_id_map = map_currency_codes_to_ids(coin_codes)
    coin_ids = ','.join(code_to_id_map.values())
    # Construct the request URL
    url = f'https://api.coingecko.com/api/v3/simple/price?ids={coin_ids}&vs_currencies=eur'

    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"An error occurred while fetching prices: {e}")
        return {}



def dashboard(request):
    if not request.user.is_authenticated:  # If user is not logged in, redirect to login
        return redirect('/accounts/login')
    else:
        cache_key_account = f'{request.user.id}_coinbase_account'
        accounts = cache.get(cache_key_account)  # This is already a Python list, not a JSON string

        if accounts is not None:
            print("loaded from cache")
            return render(request, 'dashboard.html', {
                'accounts': accounts  # Directly pass the Python list to context
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
                # Token has expired, use the refresh token to get a new access token
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
                        # Refresh token might not change, but it's good practice to update it anyway
                        expires_in=expires_in
                    )
                    # Update the access token for the current request
                    access_token = token_info['access_token']
                else:
                    # Handle the error (e.g., invalid refresh token)
                    return redirect('/error/')

            else:
                access_token = coinbase_account.access_token

            if access_token:
                # Fetch user profile information as before
                user_info_url = "https://api.coinbase.com/v2/accounts/?limit=100"
                response = requests.get(user_info_url, headers={'Authorization': f'Bearer {access_token}',
                                                                'CB-VERSION': 'YYYY-MM-DD'})

                if response.status_code == 200:
                    accounts_data = response.json()['data']

                    # Extract unique coin symbols from account data
                    coin_codes = {account['currency']['code'] for account in accounts_data if
                                  float(account['balance']['amount']) > 0.00001}

                    # Map currency codes to CoinGecko IDs
                    code_to_id_map = map_currency_codes_to_ids(coin_codes)

                    # Fetch current prices for these coins in euros using the CoinGecko IDs
                    current_prices = fetch_current_prices(
                        code_to_id_map)  # Assuming fetch_current_prices now expects a map or just codes

                    # Prepare accounts list with additional information
                    accounts_list = [{
                        'name': account['name'],
                        'balance_amount': float(account['balance']['amount']),
                        'balance_currency': account['balance']['currency'],
                        'currency_code': account['currency']['code'],
                        'currency_name': account['currency']['name'],
                        'current_price': current_prices.get(code_to_id_map.get(account['currency']['code'], ''),
                                                            {}).get('eur', 0),
                        'balance_value': float(account['balance']['amount']) * current_prices.get(
                            code_to_id_map.get(account['currency']['code'], ''), {}).get('eur', 0)
                    } for account in accounts_data if float(account['balance']['amount']) > 0.00001]

                    # Cache and render
                    cache.set(cache_key_account, accounts_list, timeout=1800)
                    return render(request, 'dashboard.html', {'accounts': accounts_list})

            return redirect('/error_redirect')


def trade_settings(request):
    return render(request, 'tradesettings.html')


def live_charts(request):
    return render(request, 'livecharts.html')


def profile(request):
    return render(request, 'profile.html')


def error_redirect(request):
    return render(request, 'error.html')


def coinbase_login(request):
    # Build the Coinbase OAuth2 URL
    parameters = {
        'response_type': 'code',
        'client_id': settings.COINBASE_CLIENT_ID,
        'redirect_uri': settings.COINBASE_REDIRECT_URI,
        'scope': 'wallet:accounts:read',
    }
    url = f"https://www.coinbase.com/oauth/authorize?response_type={parameters['response_type']}&client_id={parameters['client_id']}&redirect_uri={parameters['redirect_uri']}&scope={parameters['scope']}"
    return redirect(url)


def coinbase_callback(request):
    error = request.GET.get('error')
    if error:
        # Handle the error case
        return redirect('/error')  # Replace '/error' with your actual error handling URL

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
            # Ensure the user is authenticated before linking Coinbase account
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

                # Update user's Profile to set coinbase_connected to True
                Profile.objects.update_or_create(
                    user=request.user,
                    defaults={'coinbase_connected': True},
                )

                return redirect('/')  # Replace '/success' with your actual success URL
            else:
                # Handle the case where the user is not authenticated
                return redirect('/accounts/login/')  # Redirect to login page or appropriate URL
        else:
            # Handle error in token exchange
            return redirect('/error_redirect')  # Replace '/error' with your actual error handling URL
    else:
        # No code was provided
        return redirect('/error_redirect')


def update_dark_mode(request):
    user_id = request.POST.get('user_id')
    print(user_id)
    dark_mode = request.POST.get('dark_mode') == 'true'  # Convert string to boolean
    profile = Profile.objects.get(user__id=user_id)
    profile.dark_mode = dark_mode
    profile.save()
    return JsonResponse({'success': True})
