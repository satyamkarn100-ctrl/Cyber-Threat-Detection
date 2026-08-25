async function scanEmail() {

    let email = document.getElementById("email_input");
    let result = document.getElementById("result");
    if (email.value.trim() === "") {
        result.innerText = "⚠️ Please enter an email before scanning";
        return;
    }
    let response = await fetch("http://127.0.0.1:8000/scan-email", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            email_text: email.value
        })
    });

    let data = await response.json();
    result.innerText =
        data.status + " - " + data.phishing_probability;
}


async function scanURL() {

    let url = document.getElementById("url_input");
    let result = document.getElementById("url_result");
    if (url.value.trim() === "") {
        result.innerText = "⚠️ Please enter a URL before scanning";
        return;
    }
    try {
        let checkURL = new URL(url.value);
        if (
            checkURL.protocol !== "http:" &&
            checkURL.protocol !== "https:"
        ) {
            result.innerText = "⚠️ Please enter a valid URL";
            return;
        }
    } catch {
        result.innerText = "⚠️ Please enter a valid URL";
        return;
    }
    let response = await fetch("http://127.0.0.1:8000/scan-url", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            link: url.value
        })
    });
    let data = await response.json();
    result.innerText = data.status;
}
