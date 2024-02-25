function redirect() {
    var currentUrl = window.location.href;
    var newUrl = currentUrl.replace('/register/', '/accounts/login/');
    window.location.href = newUrl;
}

$(document).ready(function () {
    // Check if the email popup value exists and is not empty
    const emailPopupValue = '{{ messages }}';
    if (emailPopupValue) {
        // Show the email popup
        $('#email-pop-value').text(emailPopupValue);
        $('#email-popup').show();
    }

    // Close button functionality
    $('.close-btn').click(function () {
        $('#email-popup').hide();
    });
});