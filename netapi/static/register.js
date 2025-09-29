// static/register.js

document.addEventListener("DOMContentLoaded", () => {
    const form = document.getElementById("registerForm");
    const msgBox = document.getElementById("registerMessage");

    form.addEventListener("submit", async (e) => {
        e.preventDefault();

        // Formulardaten erfassen
        const data = {
            username: document.getElementById("username").value.trim(),
            password: document.getElementById("password").value.trim(),
            email: document.getElementById("email").value.trim(),
            address: document.getElementById("address").value.trim(),
            birthdate: document.getElementById("birthdate").value.trim(),
        };

        // Pflichtfeldprüfung
        if (!data.username || !data.password || !data.email) {
            showMessage("Bitte alle Pflichtfelder ausfüllen.", "error");
            return;
        }

        try {
            const res = await fetch("/register", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(data),
            });

            const result = await res.json();
            if (result.ok) {
                showMessage("Registrierung erfolgreich – jetzt kannst du dich einloggen.", "success");
                form.reset();
            } else {
                showMessage(result.error || "Ein unerwarteter Fehler ist aufgetreten.", "error");
            }
        } catch (err) {
            console.error(err);
            showMessage("Der Server ist aktuell nicht erreichbar.", "error");
        }
    });

    function showMessage(msg, type) {
        msgBox.textContent = msg;
        msgBox.className = type; // CSS: .success {color:green}, .error {color:red}
    }
});