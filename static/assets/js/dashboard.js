document.addEventListener('DOMContentLoaded', function() {
    // Check if accountsData is defined to avoid reference errors
    if (typeof accountsData !== 'undefined') {


        let total_wallet_value = 0
        accountsData.forEach(function(account) {
            console.log('Account Name:', account.name);
            console.log('Balance Amount:', account.balance_amount, account.balance_currency);
            console.log('Currency Code:', account.currency_code);
            console.log('Currency Name:', account.currency_name);
            console.log('Wallet Value', account.balance_value)
            total_wallet_value = total_wallet_value + account.balance_value
        });
        console.log('Total Value', total_wallet_value)
        document.getElementById('total_wallet_value').innerHTML = "€" + total_wallet_value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    }

    const settingsLink = document.getElementById('settingsLink');
    if (settingsLink) {
        settingsLink.addEventListener('click', function() {
            if (window.innerWidth < 868) {
                window.location.href = '/profile';
            } else {
                revealProfile();
            }
        });
    }
});

