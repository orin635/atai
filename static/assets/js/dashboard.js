document.addEventListener('DOMContentLoaded', function() {
    // Check if accountsData is defined to avoid reference errors
    if (typeof accountsData !== 'undefined') {



        accountsData.forEach(function(account) {
            console.log('Account Name:', account.name);
            console.log('Balance Amount:', account.balance_amount, account.balance_currency);
            console.log('Currency Code:', account.currency_code);
            console.log('Currency Name:', account.currency_name);
        });
    }
});