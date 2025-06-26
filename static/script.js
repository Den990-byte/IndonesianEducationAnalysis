document.addEventListener("DOMContentLoaded", function () {
    // Set a static world map view
    const map = L.map("map", {
        zoomControl: false,
        dragging: false,
        scrollWheelZoom: false,
        doubleClickZoom: false,
        boxZoom: false,
        touchZoom: false,
      }).setView([20, 0], 2);
      
    setTimeout(() => {
        map.invalidateSize();
      }, 200);

    // Replace the fetchDataFiles function with:
function fetchDataFiles() {
    fetch('/api/data-files')
        .then(response => response.json())
        .then(files => {
            loadDataFiles(files);
        })
        .catch(error => {
            console.error('Error loading data files:', error);
            document.getElementById('data-list-container').innerHTML = 
                '<div class="no-results">Error loading data files</div>';
        });
}

// And replace the loadTableData function's setTimeout with:
fetch(`/api/data-file/${file.name}`)
    .then(response => response.json())
    .then(result => {
        renderTable(container, result.headers, result.data, file);
    })
    .catch(error => {
        container.innerHTML = `<div class="no-results">Error loading data: ${error}</div>`;
    });
  
    // Add base tiles
    L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
        attribution: '&copy; OpenStreetMap & CartoDB',
        subdomains: 'abcd',
        maxZoom: 19
    })
  
    let currentLayerGroup = L.layerGroup().addTo(map);
  
    // Load default dataset
    loadMapData("IQ");
  
    // Icon click listeners
    document.querySelectorAll(".map-icon").forEach((icon) => {
      icon.addEventListener("click", () => {
        const type = icon.getAttribute("data-type");
        loadMapData(type);
      });
    });
  
    // Data loader
    function loadMapData(type) {
      fetch(`/api/world-data?type=${dataType}`)
        .then((res) => res.json())
        .then((data) => {
          // Clear old markers
          currentLayerGroup.clearLayers();
  
          data.forEach((item) => {
            const lat = parseFloat(item.lat);
            const lon = parseFloat(item.lon);
            const value = item.Value || "N/A";
            const country = item.Country || "Unknown";
  
            if (!isNaN(lat) && !isNaN(lon)) {
              const marker = L.circleMarker([lat, lon], {
                radius: 5,
                fillColor: "#007bff",
                color: "#000",
                weight: 1,
                opacity: 1,
                fillOpacity: 0.8
              });
  
              marker.bindTooltip(
                `<strong>${country}</strong><br>Value: ${value}`,
                { direction: "top", offset: [0, -5], permanent: false, opacity: 0.9 }
              );
  
              currentLayerGroup.addLayer(marker);
            }
          });
        });
    }
  });