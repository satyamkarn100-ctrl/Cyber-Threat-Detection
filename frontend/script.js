async function scanEmail() {
    let email = document.getElementById("email_input");
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
    document.getElementById('result').innerText =
        data.status + " - " + data.confidence;
}
