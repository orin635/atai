document.addEventListener("DOMContentLoaded", function() {
    const pfpLink = document.getElementById("h-nav-pfp");
    const pfpDropdown = document.getElementById("pfp-dropdown");
    const notificationIcon = document.getElementById("h-nav-notification");
    const notificationDropdown = document.getElementById("notification-dropdown");

    // Event listener for clicking on the profile picture link
    pfpLink.addEventListener("click", function(event) {
        event.preventDefault();
        revealDropdown(pfpDropdown);
    });

    // Event listener for clicking on the notification icon
    notificationIcon.addEventListener("click", function(event) {
        event.preventDefault();
        revealDropdown(notificationDropdown);
    });

    // Event listener for clicking anywhere in the document
    document.addEventListener("click", function(event) {
        const isPfpLinkClicked = event.target === pfpLink || pfpLink.contains(event.target);
        const isNotificationIconClicked = event.target === notificationIcon || notificationIcon.contains(event.target);

        // If the click is not on the profile picture link, the notification icon, or their respective dropdowns, hide the dropdowns
        if (!isPfpLinkClicked) {
            hideDropdown(pfpDropdown);
        }
        if (!isNotificationIconClicked){
            hideDropdown(notificationDropdown);
        }
    });
});

function revealDropdown(dropdown){
    console.log("Dropdown revealed");
    dropdown.style.display = "block";
}

function hideDropdown(dropdown){
    dropdown.style.display = "none";
}

function revealSettings(){
    document.getElementById("settings-popup").style.display = "block";
}

function hideSettings(){
    document.getElementById("settings-popup").style.display = "none";
}