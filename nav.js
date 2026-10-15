// Nicholas - Tasks 2.10 and 2.11: login check + navbar user info for the placeholder pages.
// Same logic as Anuska's dashboard script (2.4 and 2.5), copied here so other pages can use it

const token = localStorage.getItem("token");

if (!token) {
    window.location.replace("signin.html");
} else {
    fetch("/api/auth/me", {
        headers: { "Authorization": "Bearer " + token }
    })
    .then(response => {
        if (!response.ok) {
            throw new Error("Unable to load user information");
        }
        return response.json();
    })
    .then(data => {
        document.getElementById("userName").textContent = data.name;
        document.getElementById("businessName").textContent = data.business_name;
    })
    .catch(error => {
        console.error(error);
    });
}
