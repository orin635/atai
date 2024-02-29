function updateDarkModeMobile(userId) {
    console.log("UpdateDarkmodeMobile")
    const csrftoken = getCookieMobile('csrftoken');
    const isChecked = $('#dark_mode_mobile').is(':checked');
    console.log(isChecked)
    $.ajax({
        url: '/update-dark-mode/',
        type: 'POST',
        data: {
            'user_id': userId,
            'dark_mode': isChecked
        },
        headers: {'X-CSRFToken': csrftoken},
        success: function(response) {
            window.location.reload();
        },
        error: function(error) {
            console.error('Error updating dark mode.');
        }
    });
}

function getCookieMobile(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}