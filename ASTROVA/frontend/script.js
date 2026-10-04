// ============================================================
// ASTROVA FRONTEND
// ============================================================

// When Flask serves the dashboard, use its origin. Keep the port-5000
// fallback so the frontend also works from a separate live-server port.
const API_BASE =
    window.location.port === "5000"
        ? window.location.origin
        : "http://127.0.0.1:5000";


// ============================================================
// MAP
// ============================================================

let map = null;
let prospectivityLayer = null;
let centerMarker = null;
let latestAnalysis = {
    score: null,
    mineral: null,
    plan: []
};

const MINERAL_OPERATION_PROFILES = {
    Manganese: { capacityFactor: 1.00, excavators: 4, drills: 2, loaders: 2, dozers: 1, tankers: 2, fuelFactor: 1.00, waterFactor: 1.00, energyFactor: 1.00, activity: "Bulk extraction and haulage" },
    Nickel: { capacityFactor: 0.78, excavators: 3, drills: 3, loaders: 2, dozers: 2, tankers: 3, fuelFactor: 1.14, waterFactor: 1.28, energyFactor: 1.22, activity: "Selective extraction and grade control" },
    Cobalt: { capacityFactor: 0.56, excavators: 2, drills: 2, loaders: 1, dozers: 1, tankers: 1, fuelFactor: 0.72, waterFactor: 0.68, energyFactor: 0.82, activity: "Careful benching and stockpile sorting" }
};

function getMineralOperationProfile(mineral) {
    return MINERAL_OPERATION_PROFILES[mineral] || MINERAL_OPERATION_PROFILES.Manganese;
}


// Initialize map only once
function initializeMap() {

    if (map !== null) {
        return;
    }

    map = L.map("map", {
        preferCanvas: true,
        zoomControl: true
    }).setView(
        [12.9716, 77.5946],
        7
    );


    L.tileLayer(
        "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
        {
            maxZoom: 19,
            attribution: "&copy; OpenStreetMap contributors"
        }
    ).addTo(map);

    // Show the default Bengaluru analysis point before the first request.
    centerMarker = L.marker([12.9716, 77.5946]).addTo(map);

    // A map click becomes the next analysis location for the selected mineral.
    map.on("click", function (event) {
        const latitudeInput = document.getElementById("latitude");
        const longitudeInput = document.getElementById("longitude");

        if (latitudeInput && longitudeInput) {
            latitudeInput.value = event.latlng.lat.toFixed(4);
            longitudeInput.value = event.latlng.lng.toFixed(4);
            analyzeRegion();
        }
    });

}


// ============================================================
// PROSPECTIVITY COLOR
// ============================================================

function getProspectivityColor(score) {

    if (score >= 70) {
        return "#ff4d4d";
    }

    if (score >= 40) {
        return "#ff9f43";
    }

    return "#35d07f";
}


// ============================================================
// DRAW ONE CIRCULAR PROSPECTIVITY REGION
// ============================================================

function drawProspectivityZone(
    latitude,
    longitude,
    score
) {

    if (!map) {
        initializeMap();
    }


    // Remove previous circle and marker
    if (prospectivityLayer) {
        map.removeLayer(prospectivityLayer);
        prospectivityLayer = null;
    }

    if (centerMarker) {
        map.removeLayer(centerMarker);
        centerMarker = null;
    }


    const color = getProspectivityColor(score);


    // ONE LARGE CIRCLE
    const circle = L.circle(
        [latitude, longitude],
        {
            radius: 18000,

            color: color,

            fillColor: color,

            fillOpacity: 0.20,

            weight: 2
        }
    );


    // Center marker
    centerMarker = L.circleMarker(
        [latitude, longitude],
        {
            radius: 7,

            color: "#ffffff",

            weight: 2,

            fillColor: color,

            fillOpacity: 1
        }
    );


    prospectivityLayer = L.layerGroup([
        circle
    ]);


    prospectivityLayer.addTo(map);

    centerMarker.addTo(map);


    // Move map to selected region
    map.setView(
        [latitude, longitude],
        9,
        {
            animate: true
        }
    );

}


// ============================================================
// UPDATE PROSPECTIVITY DISPLAY
// ============================================================

function updateProspectivityDisplay(
    score,
    status
) {

    const prospectivityElement =
        document.getElementById("prospectivity");

    const statusElement =
        document.getElementById("prospectivityStatus");


    // IMPORTANT:
    // The HTML uses id="prospectivity".
    // This is the element that must receive the percentage.

    if (prospectivityElement) {

        prospectivityElement.textContent =
            `${Number(score).toFixed(1)}%`;

    }


    if (statusElement) {

        statusElement.textContent =
            status || "UNKNOWN";

    }

}


function updateAnalysisLocation(mineral, latitude, longitude) {

    const selectedMineral = document.getElementById("selectedMineral");
    const selectedLatitude = document.getElementById("selectedLatitude");
    const selectedLongitude = document.getElementById("selectedLongitude");

    if (selectedMineral) {
        selectedMineral.textContent = mineral;
    }

    if (selectedLatitude) {
        selectedLatitude.textContent = Number(latitude).toFixed(4);
    }

    if (selectedLongitude) {
        selectedLongitude.textContent = Number(longitude).toFixed(4);
    }

    document.querySelectorAll(".detail-selector").forEach(function (panel) {
        panel.querySelector("[data-selector-mineral]").value = String(mineral).toLowerCase();
        panel.querySelector("[data-selector-latitude]").value = Number(latitude).toFixed(4);
        panel.querySelector("[data-selector-longitude]").value = Number(longitude).toFixed(4);
        panel.querySelector("[data-selector-status]").textContent = `${mineral} · ${Number(latitude).toFixed(4)}, ${Number(longitude).toFixed(4)}`;
    });

}

function createDetailSelectors() {
    document.querySelectorAll('.app-view[data-view="weather"], .app-view[data-view="resources"], .app-view[data-view="production"], .app-view[data-view="risk"]').forEach(function (view) {
        const section = view.querySelector(".detail-section");
        if (!section || section.querySelector(".detail-selector")) {
            return;
        }

        const selector = document.createElement("div");
        selector.className = "detail-selector";
        selector.innerHTML = `
            <div class="detail-selector-title"><span>ANALYSIS LOCATION</span><strong data-selector-status>Choose a mineral and location</strong></div>
            <label>MINERAL<select data-selector-mineral>
                <option value="manganese">Manganese</option>
                <option value="nickel">Nickel</option>
                <option value="cobalt">Cobalt</option>
            </select></label>
            <label>LATITUDE<input data-selector-latitude type="number" value="12.9716" step="0.0001"></label>
            <label>LONGITUDE<input data-selector-longitude type="number" value="77.5946" step="0.0001"></label>
            <button type="button">ANALYZE REGION</button>`;

        selector.querySelector("button").addEventListener("click", function () {
            runPanelAnalysis(this);
        });
        section.querySelector(".detail-heading").after(selector);
    });
}

function runPanelAnalysis(button) {
    const panel = button.closest(".detail-selector");
    document.getElementById("mineral").value = panel.querySelector("[data-selector-mineral]").value;
    document.getElementById("latitude").value = panel.querySelector("[data-selector-latitude]").value;
    document.getElementById("longitude").value = panel.querySelector("[data-selector-longitude]").value;
    analyzeRegion();
}


// ============================================================
// MAIN ANALYSIS
// ============================================================

async function analyzeRegion() {

    const mineralElement =
        document.getElementById("mineral");

    const latitudeElement =
        document.getElementById("latitude");

    const longitudeElement =
        document.getElementById("longitude");

    const button =
        document.getElementById("analyzeBtn");

    const message =
        document.getElementById("message");

    // Avoid overlapping API requests when users click the map repeatedly.
    if (button.disabled) {
        return;
    }


    const mineral =
        mineralElement.value;

    const latitude =
        parseFloat(latitudeElement.value);

    const longitude =
        parseFloat(longitudeElement.value);


    // Validate coordinates
    if (
        Number.isNaN(latitude) ||
        Number.isNaN(longitude)
    ) {

        message.textContent =
            "Please enter valid latitude and longitude.";

        return;
    }


    // Disable button during analysis
    button.disabled = true;

    button.textContent =
        "ANALYZING...";


    message.textContent =
        "Running ASTROVA AI analysis...";


    try {

        // ----------------------------------------------------
        // CALL FLASK BACKEND
        // ----------------------------------------------------

        const response =
            await fetch(
                `${API_BASE}/analyze`,
                {
                    method: "POST",

                    headers: {
                        "Content-Type": "application/json"
                    },

                    body: JSON.stringify({

                        mineral: mineral,

                        latitude: latitude,

                        longitude: longitude,

                        analysis_run: Date.now()

                    })
                }
            );


        if (!response.ok) {

            throw new Error(
                `Backend returned ${response.status}`
            );

        }


        const data =
            await response.json();


        console.log(
            "ASTROVA analysis response:",
            data
        );


        if (data.error) {

            throw new Error(
                data.error
            );

        }


        // ----------------------------------------------------
        // GET PROSPECTIVITY SCORE
        // ----------------------------------------------------

        const score =
            Number(
                data.prospectivity_score
            );


        const status =
            data.prospectivity ||
            "UNKNOWN";


        // Make sure score is valid
        if (Number.isNaN(score)) {

            throw new Error(
                "Backend did not return a valid prospectivity score."
            );

        }

        latestAnalysis = {
            score: score,
            mineral: data.mineral || mineral,
            latitude: latitude,
            longitude: longitude,
            plan: data.production_plan || []
        };


        // ----------------------------------------------------
        // DISPLAY THE BIG PERCENTAGE
        // ----------------------------------------------------

        updateProspectivityDisplay(
            score,
            status
        );

        updateAnalysisLocation(
            data.mineral || mineral,
            latitude,
            longitude
        );


        // ----------------------------------------------------
        // DRAW MAP CIRCLE
        // ----------------------------------------------------

        drawProspectivityZone(
            latitude,
            longitude,
            score
        );


        // ----------------------------------------------------
        // WEATHER
        // ----------------------------------------------------

        await loadWeather(
            latitude,
            longitude
        );


        // ----------------------------------------------------
        // PRODUCTION
        // ----------------------------------------------------

        updateProduction(
            score,
            data.production_plan || [],
            data.mineral || mineral
        );


        // ----------------------------------------------------
        // RESOURCE OPTIMIZATION
        // ----------------------------------------------------

        updateResources(
            score,
            data.mineral || mineral
        );


        // ----------------------------------------------------
        // RISK
        // ----------------------------------------------------

        updateRisk(
            score
        );


        // ----------------------------------------------------
        // SUCCESS MESSAGE
        // ----------------------------------------------------

        message.textContent =
            `Analysis complete — ${score.toFixed(1)}% prospectivity (${status}).`;


    } catch (error) {

        console.error(
            "ASTROVA analysis error:",
            error
        );


        message.textContent =
            `Analysis failed: ${error.message}`;


    } finally {

        button.disabled = false;

        button.textContent =
            "ANALYZE REGION →";

    }

}


// ============================================================
// WEATHER
// ============================================================

let weatherController = null;


async function loadWeather(
    latitude,
    longitude
) {

    try {

        // Cancel previous weather request
        if (weatherController) {

            weatherController.abort();

        }


        weatherController =
            new AbortController();


        const url =
            "https://api.open-meteo.com/v1/forecast" +
            `?latitude=${encodeURIComponent(latitude)}` +
            `&longitude=${encodeURIComponent(longitude)}` +
            "&current=temperature_2m,relative_humidity_2m," +
            "precipitation,wind_speed_10m,weather_code" +
            "&daily=weather_code,temperature_2m_max,temperature_2m_min," +
            "precipitation_probability_max,precipitation_sum," +
            "wind_speed_10m_max,wind_gusts_10m_max,uv_index_max" +
            "&forecast_days=5" +
            "&timezone=auto";


        const response =
            await fetch(
                url,
                {
                    signal:
                        weatherController.signal
                }
            );


        if (!response.ok) {

            throw new Error(
                "Weather service unavailable"
            );

        }


        const data =
            await response.json();


        const current =
            data.current;


        // Temperature
        const temperature =
            document.getElementById(
                "temperature"
            );

        if (temperature) {

            temperature.textContent =
                `${Number(
                    current.temperature_2m
                ).toFixed(1)}°C`;

        }


        // Humidity
        const humidity =
            document.getElementById(
                "humidity"
            );

        if (humidity) {

            humidity.textContent =
                `${Math.round(
                    current.relative_humidity_2m
                )}%`;

        }


        // Wind
        const wind =
            document.getElementById(
                "wind"
            );

        if (wind) {

            wind.textContent =
                `${Number(
                    current.wind_speed_10m
                ).toFixed(1)} km/h`;

        }


        // Rainfall / precipitation
        const rainfall =
            document.getElementById(
                "rainfall"
            );

        if (rainfall) {

            rainfall.textContent =
                `${Number(
                    current.precipitation || 0
                ).toFixed(1)} mm`;

        }


        // Weather condition
        const condition =
            document.getElementById(
                "weatherCondition"
            );

        if (condition) {

            condition.textContent =
                getWeatherDescription(
                    current.weather_code
                );

        }


        // Mining impact
        const impact =
            calculateWeatherImpact(
                current
            );


        const miningImpact =
            document.getElementById(
                "miningImpact"
            );

        if (miningImpact) {

            miningImpact.textContent =
                impact.label;

        }


        // Weather KPI
        const weatherImpact =
            document.getElementById(
                "weatherImpact"
            );

        if (weatherImpact) {

            weatherImpact.textContent =
                impact.label;

        }

        renderWeatherForecast(data.daily);


        return current;


    } catch (error) {

        // Ignore cancellation errors
        if (
            error.name === "AbortError"
        ) {

            return;

        }


        console.error(
            "Weather error:",
            error
        );


        const condition =
            document.getElementById(
                "weatherCondition"
            );

        if (condition) {

            condition.textContent =
                "Weather unavailable";

        }

        const forecast = document.getElementById("weatherForecast");

        if (forecast) {
            forecast.innerHTML =
                "<p>Five-day weather forecast is currently unavailable.</p>";
        }

    }

}


function getForecastOperationalNote(rain, wind, gust, uvIndex) {

    if (rain >= 10 || gust >= 45) {
        return "High risk · review haulage and outdoor work";
    }

    if (rain >= 3 || wind >= 30 || uvIndex >= 8) {
        return "Monitor · adjust shifts and road checks";
    }

    return "Favourable · standard operating plan";

}


function renderWeatherForecast(daily) {

    const forecast = document.getElementById("weatherForecast");

    if (!forecast || !daily || !Array.isArray(daily.time)) {
        return;
    }

    forecast.innerHTML = daily.time.slice(0, 5).map(function (day, index) {
        const date = new Date(`${day}T00:00:00`);
        const maxTemperature = Number(daily.temperature_2m_max[index]);
        const minTemperature = Number(daily.temperature_2m_min[index]);
        const rain = Number(daily.precipitation_sum[index] || 0);
        const rainChance = Number(
            daily.precipitation_probability_max[index] || 0
        );
        const wind = Number(daily.wind_speed_10m_max[index] || 0);
        const gust = Number(daily.wind_gusts_10m_max[index] || 0);
        const uvIndex = Number(daily.uv_index_max[index] || 0);
        const weather = getWeatherDescription(daily.weather_code[index]);
        const operationalNote = getForecastOperationalNote(
            rain,
            wind,
            gust,
            uvIndex
        );

        return `
            <article class="forecast-day">
                <span>DAY ${index + 1} · ${date.toLocaleDateString(undefined, {
                    month: "short",
                    day: "numeric"
                })}</span>
                <strong>${maxTemperature.toFixed(0)}° / ${minTemperature.toFixed(0)}°</strong>
                <small>${weather}<br>Rain: ${rain.toFixed(1)} mm (${rainChance}%)<br>Wind: ${wind.toFixed(0)} km/h · UV ${uvIndex.toFixed(0)}</small>
                <small class="forecast-impact">${operationalNote}</small>
            </article>
        `;
    }).join("");

}


// ============================================================
// WEATHER DESCRIPTION
// ============================================================

function getWeatherDescription(
    code
) {

    const weatherCodes = {

        0: "Clear sky",

        1: "Mainly clear",

        2: "Partly cloudy",

        3: "Overcast",

        45: "Fog",

        48: "Depositing rime fog",

        51: "Light drizzle",

        53: "Moderate drizzle",

        55: "Dense drizzle",

        61: "Slight rain",

        63: "Moderate rain",

        65: "Heavy rain",

        71: "Slight snowfall",

        73: "Moderate snowfall",

        75: "Heavy snowfall",

        80: "Rain showers",

        81: "Moderate rain showers",

        82: "Violent rain showers",

        95: "Thunderstorm",

        96: "Thunderstorm with hail",

        99: "Thunderstorm with heavy hail"

    };


    return (
        weatherCodes[code] ||
        "Current conditions"
    );

}


// ============================================================
// WEATHER IMPACT
// ============================================================

function calculateWeatherImpact(
    current
) {

    const rainfall =
        Number(
            current.precipitation || 0
        );

    const wind =
        Number(
            current.wind_speed_10m || 0
        );


    let impact =
        0;


    // Prototype operational assumptions
    if (rainfall > 10) {

        impact += 15;

    } else if (rainfall > 5) {

        impact += 8;

    } else if (rainfall > 1) {

        impact += 3;

    }


    if (wind > 40) {

        impact += 12;

    } else if (wind > 25) {

        impact += 6;

    }


    impact =
        Math.min(
            impact,
            40
        );


    let label =
        "LOW";


    if (impact >= 25) {

        label =
            "HIGH";

    } else if (impact >= 10) {

        label =
            "MODERATE";

    }


    return {

        percent: impact,

        label: label

    };

}


// ============================================================
// PRODUCTION
// ============================================================

function updateProduction(
    prospectivityScore,
    productionPlan = [],
    mineral = latestAnalysis.mineral
) {

    const profile = getMineralOperationProfile(mineral);
    const target = 10000 * profile.capacityFactor;


    // Prototype demonstration estimate
    const baseFactor =
        0.78 +
        (prospectivityScore / 100) * 0.17;


    const forecast =
        Math.round(
            target * baseFactor
        );


    const gap =
        Math.max(
            target - forecast,
            0
        );


    const shortfall =
        (gap / target) * 100;


    const production =
        document.getElementById(
            "productionValue"
        );

    if (production) {

        production.textContent =
            `${forecast.toLocaleString()} t`;

    }


    const forecastProduction =
        document.getElementById(
            "forecastProduction"
        );

    if (forecastProduction) {

        forecastProduction.textContent =
            `${forecast.toLocaleString()} t`;

    }


    const productionGap =
        document.getElementById(
            "productionGap"
        );

    if (productionGap) {

        productionGap.textContent =
            `${gap.toLocaleString()} t`;

    }


    const shortfallElement =
        document.getElementById(
            "shortfall"
        );

    if (shortfallElement) {

        shortfallElement.textContent =
            `${shortfall.toFixed(1)}%`;

    }

    const forecastDisplay = document.getElementById("forecastDisplay");
    const shortfallDisplay = document.getElementById("shortfallDisplay");

    if (forecastDisplay) {
        forecastDisplay.textContent = `${forecast.toLocaleString()} t`;
    }

    if (shortfallDisplay) {
        const readiness = Math.min(
            98,
            Math.round(70 + prospectivityScore * 0.25)
        );
        shortfallDisplay.textContent = `${readiness}%`;
    }

    renderProductionPlan(productionPlan);

}


function renderProductionPlan(plan) {

    const planElement = document.getElementById("productionPlan");
    const averageElement = document.getElementById("dailyAverageDisplay");
    const totalElement = document.getElementById("forecastDisplay");

    if (!planElement || !Array.isArray(plan) || plan.length === 0) {
        return;
    }

    const totalTonnes = plan.reduce(function (total, day) {
        return total + Number(day.planned_tonnes || 0);
    }, 0);

    if (averageElement) {
        averageElement.textContent =
            `${Math.round(totalTonnes / plan.length).toLocaleString()} t`;
    }

    if (totalElement) {
        totalElement.textContent = `${totalTonnes.toLocaleString()} t`;
    }

    planElement.innerHTML = `<ol class="production-list">${plan.map(function (day) {
        const date = new Date(`${day.date}T00:00:00`);
        const dateLabel = date.toLocaleDateString(undefined, {
            month: "short",
            day: "numeric"
        });

        return `
            <li class="production-day">
                <span>${day.day} · ${dateLabel}</span>
                <strong>${Number(day.planned_tonnes).toLocaleString()} t</strong>
                <small>${day.activity}</small>
            </li>
        `;
    }).join("")}</ol>`;

}


// ============================================================
// RESOURCE OPTIMIZATION
// ============================================================

function updateResources(
    prospectivityScore,
    mineral = latestAnalysis.mineral
) {

    const profile = getMineralOperationProfile(mineral);

    const workers =
        Math.round(
            (80 + prospectivityScore * 0.10) * profile.capacityFactor
        );


    const trucks =
        Math.round(
            (10 + prospectivityScore * 0.03) * profile.capacityFactor
        );


    const fuel =
        Math.round(
            (4200 + prospectivityScore * 9) * profile.fuelFactor
        );


    const workersElement =
        document.getElementById(
            "workersOptimized"
        );

    if (workersElement) {

        workersElement.textContent =
            workers;

    }


    const trucksElement =
        document.getElementById(
            "trucksOptimized"
        );

    if (trucksElement) {

        trucksElement.textContent =
            trucks;

    }


    const fuelElement =
        document.getElementById(
            "fuelOptimized"
        );

    if (fuelElement) {

        fuelElement.textContent =
            fuel;

    }

    const workersDisplay = document.getElementById("workersDisplay");
    const trucksDisplay = document.getElementById("trucksDisplay");
    const fuelDisplay = document.getElementById("fuelDisplay");

    if (workersDisplay) {
        workersDisplay.textContent = `${workers} workers`;
    }

    if (trucksDisplay) {
        trucksDisplay.textContent = `${trucks} vehicles`;
    }

    if (fuelDisplay) {
        fuelDisplay.textContent = `${fuel.toLocaleString()} L/day`;
    }

    renderResourcePlan(prospectivityScore, mineral);

}


// ============================================================
// OPTIMIZE RESOURCES BUTTON
// ============================================================

function optimizeResources() {

    const message =
        document.getElementById(
            "message"
        );


    if (message) {

        message.textContent =
            "Resource optimization updated using the current prospectivity scenario.";

    }

    if (latestAnalysis.score !== null) {
        renderResourcePlan(latestAnalysis.score, latestAnalysis.mineral);
    }

}


function renderResourcePlan(prospectivityScore, mineral = latestAnalysis.mineral) {

    const planElement = document.getElementById("resourcePlan");

    if (!planElement) {
        return;
    }

    const profile = getMineralOperationProfile(mineral);
    const workforce = Math.round((80 + prospectivityScore * 0.10) * profile.capacityFactor);
    const trucks = Math.max(3, Math.round((10 + prospectivityScore * 0.03) * profile.capacityFactor));
    const baseFuel = Math.round((4200 + prospectivityScore * 9) * profile.fuelFactor);

    planElement.innerHTML = Array.from({ length: 5 }, function (_, index) {
        const dayFactor = [0.92, 1, 1.06, 0.97, 1.03][index];
        const fuel = Math.round(baseFuel * dayFactor);
        const energy = Math.round((2800 + prospectivityScore * 8) * profile.energyFactor * dayFactor);
        const water = Math.round((62 + prospectivityScore * 0.32) * profile.waterFactor * dayFactor);
        const trips = Math.round(trucks * 2.5 * dayFactor);

        return `
            <li class="resource-day">
                <strong>DAY ${index + 1}</strong>
                <span><b>${mineral} machines</b><br>${profile.excavators} excavators · ${profile.drills} drills · ${profile.loaders} loaders · ${profile.dozers} dozers · ${trucks} haul trucks · ${profile.tankers} water tankers</span>
                <span><b>People &amp; fuel</b><br>${workforce} people · ${fuel.toLocaleString()} L diesel · 8 operating hours</span>
                <span><b>${profile.activity}</b><br>${energy.toLocaleString()} kWh · ${water} kL water · ${trips} haul trips</span>
            </li>
        `;
    }).join("");

}


function runScenario() {

    const result = document.getElementById("scenarioResult");

    if (latestAnalysis.score === null || latestAnalysis.plan.length === 0) {
        result.textContent = "Run a location analysis first, then test a scenario.";
        return;
    }

    const rainfall = Number(document.getElementById("scenarioRainfall").value);
    const equipment = Number(document.getElementById("scenarioEquipment").value);
    const target = Number(document.getElementById("scenarioTarget").value);
    const hours = Number(document.getElementById("scenarioHours").value);
    const weatherFactor = Math.max(0.55, 1 - rainfall * 0.012);
    const capacityFactor = (equipment / 100) * (hours / 8) * weatherFactor;
    const scenarioPlan = latestAnalysis.plan.map(function (day) {
        return {
            ...day,
            planned_tonnes: Math.max(
                0,
                Math.round(Number(day.planned_tonnes) * capacityFactor)
            )
        };
    });
    const projected = scenarioPlan.reduce(function (total, day) {
        return total + day.planned_tonnes;
    }, 0);
    const gap = Math.max(0, target - projected);
    const risk = Math.min(
        100,
        Math.round((100 - equipment) + rainfall * 1.3 + Math.max(0, 8 - hours) * 5 + (gap / target) * 45)
    );

    renderProductionPlan(scenarioPlan);
    renderResourcePlan(latestAnalysis.score * capacityFactor, latestAnalysis.mineral);

    const riskDisplay = document.getElementById("riskDisplay");
    const riskText = document.getElementById("riskDescriptionDisplay");

    if (riskDisplay) {
        riskDisplay.textContent = `${risk}/100`;
    }

    if (riskText) {
        riskText.textContent = risk >= 55
            ? "Scenario risk is elevated: review equipment, weather, and target constraints."
            : "Scenario risk is manageable under the selected operating constraints.";
    }

    result.textContent = `Projected five-day output: ${projected.toLocaleString()} t. Target gap: ${gap.toLocaleString()} t. Scenario risk: ${risk}/100.`;

}


function explainAnalysis(topic) {

    const response = document.getElementById("copilotResponse");

    if (latestAnalysis.score === null) {
        response.textContent = "Run an analysis first so the copilot can explain the current scenario.";
        return;
    }

    const score = latestAnalysis.score.toFixed(1);
    const mineral = latestAnalysis.mineral;
    const explanations = {
        prediction: `${mineral} received a ${score}% prospectivity score from the prototype Random Forest model. The score is a screening priority, not proof of mineral concentration; field validation is the next action.`,
        shortfall: "The five-day production list is a capacity proposal. Compare its total with your target, then use the What-If controls to show how rain, equipment, and shift hours can create or reduce a gap.",
        risk: "Risk combines the current prospectivity scenario with operational conditions. Heavy rain, lower equipment availability, shorter shifts, or an ambitious target increase the scenario risk.",
        resources: "The resource plan converts the scenario into a daily starting requirement for machines, workforce, diesel, electricity, water, and haulage. Live availability data would turn this into a feasible optimization plan."
    };

    response.textContent = explanations[topic];

}


function generateExecutiveReport() {

    const response = document.getElementById("copilotResponse");
    response.textContent = "Opening the browser print dialog. Choose ‘Save as PDF’ to create an executive report of the current dashboard scenario.";
    window.setTimeout(function () {
        window.print();
    }, 100);

}


// ============================================================
// RISK
// ============================================================

function updateRisk(
    prospectivityScore
) {

    // Prototype operational risk estimate
    const riskScore =
        Math.round(
            100 -
            prospectivityScore
        );


    let riskLevel =
        "LOW";


    if (riskScore >= 70) {

        riskLevel =
            "HIGH";

    } else if (riskScore >= 40) {

        riskLevel =
            "MEDIUM";

    }


    const riskLevelElement =
        document.getElementById(
            "riskLevel"
        );

    if (riskLevelElement) {

        riskLevelElement.textContent =
            riskLevel;

    }


    const riskScoreElement =
        document.getElementById(
            "riskScore"
        );

    if (riskScoreElement) {

        riskScoreElement.textContent =
            riskScore;

    }


    const riskDescription =
        document.getElementById(
            "riskDescription"
        );

    if (riskDescription) {

        riskDescription.textContent =
            `Prototype operational risk level: ${riskLevel}. ` +
            `Risk score: ${riskScore}/100.`;

    }

    const riskDisplay = document.getElementById("riskDisplay");
    const riskDescriptionDisplay = document.getElementById(
        "riskDescriptionDisplay"
    );

    if (riskDisplay) {
        riskDisplay.textContent = `${riskScore}/100`;
    }

    if (riskDescriptionDisplay) {
        riskDescriptionDisplay.textContent =
            `Current operational risk: ${riskLevel}.`;
    }

}


// ============================================================
// PAGE LOAD
// ============================================================

document.addEventListener(
    "DOMContentLoaded",
    function () {

        initializeMap();
        createDetailSelectors();

        const earthObservationStep = document.querySelector(
            ".presentation-flow article:nth-child(2) div"
        );

        if (earthObservationStep) {
            earthObservationStep.insertAdjacentHTML(
                "beforeend",
                `<div class="spectral-band-tags">
                    <span>B2 · Blue</span><span>B3 · Green</span>
                    <span>B4 · Red</span><span>B8 · NIR</span>
                    <span>B11 · SWIR 1</span><span>B12 · SWIR 2</span>
                    <span>NDVI</span><span>NDWI</span>
                </div>`
            );
        }

        document.querySelectorAll("nav a").forEach(function (link) {
            link.addEventListener("click", function (event) {
                event.preventDefault();

                document.querySelectorAll("nav a").forEach(function (item) {
                    item.classList.remove("active");
                });
                link.classList.add("active");

                document.querySelectorAll(".app-view").forEach(function (view) {
                    view.classList.toggle(
                        "active",
                        view.dataset.view === link.dataset.view
                    );
                });

                if (link.dataset.view === "dashboard" && map) {
                    window.setTimeout(function () {
                        map.invalidateSize();
                    }, 0);
                }
            });
        });

    }
);
