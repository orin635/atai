document.addEventListener('DOMContentLoaded', function() {
  var pfpDropdown = document.getElementById('pfp-dropdown');
  var profilePicture = document.getElementById('h-nav-pfp');

  // Show dropdown when clicking on profile picture
  profilePicture.addEventListener('click', function(event) {
    event.stopPropagation(); // Prevent the click event from bubbling up

    // Toggle visibility of the dropdown
    pfpDropdown.style.display = pfpDropdown.style.display === 'none' ? 'block' : 'none';
  });

  // Hide dropdown when clicking outside of it
  document.addEventListener('click', function(event) {
    if (!pfpDropdown.contains(event.target) && event.target !== profilePicture) {
      // Click occurred outside of the dropdown and profile picture, hide the dropdown
      pfpDropdown.style.display = 'none';
    }
  });
});
