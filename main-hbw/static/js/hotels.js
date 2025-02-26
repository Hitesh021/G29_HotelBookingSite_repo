$(document).ready(function() {
    $("#searchButton").click(function() {
        const city = $("#city").val();

        // Add loading state
        const searchButton = $(this);
        searchButton.addClass("loading");
        searchButton.text("SEARCHING...");

        // Clear previous results
        $("#searchResults").empty();

        // Make AJAX request
        $.ajax({
            url: "/api/hotels",
            data: { city: city },
            type: "GET",
            dataType: "json",
            success: function(response) {
                // Remove loading state
                searchButton.removeClass("loading");
                searchButton.text("GET ME BEST PRICES");

                // Display results
                if (response.error) {
                    $("#searchResults").append("<p class='text-danger'>Error: " + response.error + "</p>");
                } else if (response.length === 0) {
                    $("#searchResults").append("<p>No hotels found.</p>");
                } else {
                    response.forEach(function(hotel) {
                        const card = `
                            <div class="hotel-card">
                                <img src="${hotel.image || 'default-hotel.jpg'}" class="hotel-image" alt="${hotel.name}">
                                <div class="hotel-info">
                                    <div class="hotel-name">${hotel.name}</div>
                                    <div class="hotel-city">${hotel.city}</div>
                                    <div class="hotel-rating">⭐ ${hotel.rating || 'N/A'}</div>
                                    <div class="hotel-price">$${hotel.price} per night</div>
                                </div>
                                <a href="#" class="book-now">Book Now</a>
                            </div>
                        `;
                        $("#searchResults").append(card);
                    });
                }
            },
            error: function(xhr, status, error) {
                // Remove loading state
                searchButton.removeClass("loading");
                searchButton.text("GET ME BEST PRICES");

                // Display error
                $("#searchResults").empty();
                $("#searchResults").append("<p class='text-danger'>Error fetching data: " + error + "</p>");
                console.error("AJAX error:", status, error);
            }
        });
    });
});

document.addEventListener('DOMContentLoaded', function() {
    const navbar = document.querySelector('.navbar');
    
    window.addEventListener('scroll', function() {
        if (window.scrollY > 50) {
            navbar.classList.add('scrolled');
        } else {
            navbar.classList.remove('scrolled');
        }
    });
});