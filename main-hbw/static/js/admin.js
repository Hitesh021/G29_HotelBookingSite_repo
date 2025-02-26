document.getElementById('booking-form').addEventListener('submit', function(event) {
    event.preventDefault();
    
    const user = document.getElementById('user').value;
    const action = document.getElementById('action').value;
    const responseElement = document.getElementById('response');

    if (!user || !action) {
        responseElement.innerText = 'Both user and action fields are required.';
        return;
    }

    responseElement.innerText = 'Processing...';

    fetch('/admin', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ user: user, action: action })
    })
    .then(response => response.json())
    .then(data => {
        responseElement.innerText = data.message;
    })
    .catch(error => {
        console.error('Error:', error);
        responseElement.innerText = 'An error occurred while processing your request. Please try again.';
    });
});
