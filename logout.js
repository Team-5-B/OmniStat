// Nicholas - Task 2.6: logout button
// Deletes the saved login token and sends the user back to sign in.

document.getElementById("logoutButton").addEventListener("click", function () {
    localStorage.removeItem("token");
    window.location.replace("signin.html");
});