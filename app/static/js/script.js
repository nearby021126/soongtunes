document.querySelector("form").addEventListener("submit", async function (event) {
    event.preventDefault();

    const userMessage = document.querySelector('input[name="message"]').value;

    try {
        const response = await fetch("/", {
            method: "POST",
            headers: { "Content-Type": "application/x-www-form-urlencoded" },
            body: new URLSearchParams({ message: userMessage })
        });

        if (response.redirected) {
            window.location.href = response.url;
        } else {
            console.error("Unexpected response: ", response);
        }
    } catch (error) {
        console.error("Error submitting the form:", error);
    }
});


async function startSpeech() {
    try {
        const response = await fetch("/recognition");
        const data = await response.json();
        document.querySelector('input[name="message"]').value = data.input_text || "No input text received";
        document.querySelector('input[name="recommendation"]').value = data.graph_response || "No recommendation available";
    } catch (error) {
        console.error("Error during recognition:", error);
        document.querySelector('input[name="message"]').value = "Error: " + error;
        document.querySelector('input[name="recommendation"]').value = "Error: Unable to fetch recommendations";
    }
}