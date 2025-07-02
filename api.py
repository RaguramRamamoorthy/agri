import streamlit as st
import folium
import datetime
import ee
from streamlit_folium import st_folium
import geemap.foliumap as geemap

# --- EE Init ---
try:
    ee.Initialize(project='ee-rrrtechie')
except Exception:
    ee.Authenticate()
    ee.Initialize(project='ee-rrrtechie')

# --- Streamlit Layout ---
st.set_page_config(layout="wide")
st.title("🌾 Sentinel-2 Crop Stress Detection")

col1, col2 = st.columns(2)

# -------- Left Panel: Dual-Layer Map (Satellite + OSM) --------
with col1:
    st.subheader("🛰️ Select Location on Satellite Map")
    st.markdown("Click to drop a red marker and auto-generate crop stress map.")

    # Create dual-layer map
    base_location = [11.0, 78.0]
    satellite_layer = folium.TileLayer(
        tiles='https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}',
        attr='Google Satellite',
        name='Google Satellite',
        control=True
    )

    osm_layer = folium.TileLayer(
        tiles='OpenStreetMap',
        name='OpenStreetMap',
        control=True
    )

    m = folium.Map(location=base_location, zoom_start=8)
    satellite_layer.add_to(m)
    osm_layer.add_to(m)
    folium.LayerControl().add_to(m)

    map_data = st_folium(m, height=50, returned_objects=["last_clicked"])

    lat, lon = None, None
    if map_data and map_data.get("last_clicked"):
        lat = map_data["last_clicked"]["lat"]
        lon = map_data["last_clicked"]["lng"]

        st.success(f"📌 Selected Location: Latitude = {lat:.6f}, Longitude = {lon:.6f}")
    else:
        st.info("Click on the map to select a location.")

# -------- Right Panel: NDVI Stress Visualization --------
with col2:
    st.subheader("🌿 NDVI Stress Zone (50m Buffer)")

    if lat and lon:
        point = ee.Geometry.Point([lon, lat])
        aoi = point.buffer(50).bounds()

        # Date Range
        end = datetime.date.today()
        start = end - datetime.timedelta(days=90)

        s2_collection = ee.ImageCollection("COPERNICUS/S2_HARMONIZED") \
            .filterBounds(aoi) \
            .filterDate(start.isoformat(), end.isoformat()) \
            .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 20))

        s2 = s2_collection.median().clip(aoi)
        band_names = s2.bandNames().getInfo()

        if "B8" in band_names and "B4" in band_names:
            ndvi = s2.normalizedDifference(["B8", "B4"]).rename("NDVI")

            def classify_ndvi(image):
                return image.expression(
                    "b('NDVI') < 0.3 ? 1 : b('NDVI') < 0.5 ? 2 : 3"
                ).rename("StressLevel")

            stress = classify_ndvi(ndvi)

            vis_params = {
                "min": 1,
                "max": 3,
                "palette": ["red", "yellow", "green"],
            }

            fmap = geemap.Map(center=[lat, lon], zoom=16)
            fmap.addLayer(stress, vis_params, "Crop Stress NDVI")
            fmap.addLayer(ee.Feature(point), {'color': 'red'}, "Selected Point")
            fmap.addLayerControl()

            fmap.to_streamlit(height=500)

            st.markdown("""
            **Legend:**
            - 🔴 `NDVI < 0.3`: Severe Stress  
            - 🟡 `NDVI < 0.5`: Moderate Stress  
            - 🟢 `NDVI >= 0.5`: Healthy  
            """)
        else:
            st.error("⚠️ Sentinel-2 bands B8 and B4 are missing for this region/date.")
    else:
        st.info("Select a location on the left map to show crop stress.")
