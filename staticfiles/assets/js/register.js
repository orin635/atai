function redirect() {
    var currentUrl = window.location.href;
    var newUrl = currentUrl.replace('/register/', '/accounts/login/');
    window.location.href = newUrl;
}

function submitForm() {
    alert("Email Submitted!");
}

// Close the popup when the close button is clicked
document.querySelector('.close-btn').addEventListener('click', function() {
    document.getElementById('email-popup').style.display = 'none';
});