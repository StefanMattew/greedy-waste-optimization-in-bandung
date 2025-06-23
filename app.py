# app.py
import streamlit as st
import osmnx as ox
import networkx as nx
import folium
import pandas as pd
from streamlit.components.v1 import html as st_html
from streamlit_javascript import st_javascript

st.set_page_config(page_title="Bandung Sampah", layout="wide")
st.title("\U0001F6AE Optimasi Tempat Sampah & TPS di Bandung")

# Load data
tps_df = pd.read_csv("data/tps_bandung_lengkap.csv")
sampah_df = pd.read_csv("data/sampah_harian_bandung.csv")

# ========== INISIALISASI SESSION STATE ==========
if "user_lat" not in st.session_state:
    st.session_state["user_lat"] = -6.89148
if "user_lon" not in st.session_state:
    st.session_state["user_lon"] = 107.61069
if "gps_set" not in st.session_state:
    st.session_state["gps_set"] = False
if "rendered_map" not in st.session_state:
    st.session_state["rendered_map"] = None

# ========== AMBIL GPS OTOMATIS DENGAN JAVASCRIPT (ASYNC) ==========
st.markdown("## 📍 Lokasi GPS Anda (Otomatis)")

coords = None
if not st.session_state["gps_set"]:
    coords = st_javascript("""await new Promise((resolve, reject) => {
      navigator.geolocation.getCurrentPosition(
        (pos) => resolve([pos.coords.latitude, pos.coords.longitude]),
        (err) => resolve(null)
      );
    });""")

if coords:
    st.session_state["user_lat"] = coords[0]
    st.session_state["user_lon"] = coords[1]
    st.session_state["gps_set"] = True
    st.success(f"Lokasi berhasil dibaca: {coords[0]:.6f}, {coords[1]:.6f}")
elif not st.session_state["gps_set"]:
    st.warning("Gagal membaca lokasi. Gunakan koordinat default atau coba aktifkan GPS di browser.")

user_lat = st.session_state["user_lat"]
user_lon = st.session_state["user_lon"]

# Slider untuk radius
radius_km = st.sidebar.slider("Jarak jaringan jalan (km)", 0.5, 2.0, 1.2, 0.1)

if st.sidebar.button("🔍 Hitung & Visualisasikan"):
    with st.spinner("🔄 Mengambil jaringan jalan dari OSM..."):
        G = ox.graph_from_point((user_lat, user_lon), dist=radius_km * 1000, network_type="walk")

    if G.number_of_nodes() == 0:
        st.error("❌ Jaringan jalan tidak ditemukan.")
        st.stop()

    m = folium.Map(location=[user_lat, user_lon], zoom_start=14)
    folium.Marker([user_lat, user_lon], tooltip="Lokasi Anda", icon=folium.Icon(color="blue")).add_to(m)

    tps_nodes = [ox.distance.nearest_nodes(G, lon, lat) for lat, lon in zip(tps_df.lat, tps_df.lon)]
    for idx, node in enumerate(tps_nodes):
        y, x = G.nodes[node]["y"], G.nodes[node]["x"]
        folium.Marker([y, x], tooltip=tps_df.loc[idx, "nama"], icon=folium.Icon(color="green", icon="trash")).add_to(m)

    sampah_nodes = [ox.distance.nearest_nodes(G, lon, lat) for lat, lon in zip(sampah_df.lat, sampah_df.lon)]
    for idx, node in enumerate(sampah_nodes):
        y, x = G.nodes[node]["y"], G.nodes[node]["x"]
        folium.CircleMarker([y, x], radius=4, color="gray", tooltip=f"TPS Harian #{int(sampah_df.loc[idx, 'id'])}").add_to(m)

    for node in sampah_nodes:
        try:
            dists = [(tps_node, nx.shortest_path_length(G, node, tps_node, weight="length")) for tps_node in tps_nodes]
            tps_near = min(dists, key=lambda p: p[1])[0]
            path = nx.shortest_path(G, node, tps_near, weight="length")
            coords_path = [(G.nodes[n]["y"], G.nodes[n]["x"]) for n in path]
            folium.PolyLine(coords_path, color="orange", weight=2).add_to(m)
        except:
            continue

    try:
        user_node = ox.distance.nearest_nodes(G, user_lon, user_lat)

        user_to_tps = [(tps_node, nx.shortest_path_length(G, user_node, tps_node, weight="length")) for tps_node in tps_nodes]
        tps_near_user, jarak_m = min(user_to_tps, key=lambda x: x[1])
        path_user = nx.shortest_path(G, user_node, tps_near_user, weight="length")
        coords_user_path = [(G.nodes[n]["y"], G.nodes[n]["x"]) for n in path_user]
        folium.PolyLine(coords_user_path, color="red", weight=4, tooltip="Jalur Anda ke TPS").add_to(m)

        tujuan_lat = G.nodes[tps_near_user]["y"]
        tujuan_lon = G.nodes[tps_near_user]["x"]
        waktu_user = jarak_m / (5000 / 60)

        st.sidebar.markdown(f"""
        ---
        ### 🛍️ Info Jalur Anda:
        - 📍 Lokasi Anda: ({user_lat:.5f}, {user_lon:.5f})
        - 🗑️ TPS Terdekat: ({tujuan_lat:.5f}, {tujuan_lon:.5f})
        - 📏 Jarak via jalan: `{jarak_m:.1f} meter`
        - 🕒 Estimasi waktu: `{waktu_user:.1f} menit`
        """)

        tps_terdekat_sorted = sorted(user_to_tps, key=lambda x: x[1])[:3]
        st.sidebar.markdown("### 📂 3 TPS Terdekat:")
        for i, (node_id, jrk) in enumerate(tps_terdekat_sorted, start=1):
            y, x = G.nodes[node_id]["y"], G.nodes[node_id]["x"]
            waktu_menit = jrk / (5000/60)
            st.sidebar.markdown(f"- {i}. ({y:.5f}, {x:.5f}) - {jrk:.0f} m ({waktu_menit:.1f} menit)")

        harian_to_user = [(s_node, nx.shortest_path_length(G, user_node, s_node, weight="length")) for s_node in sampah_nodes]
        s_near_user, jarak_s = min(harian_to_user, key=lambda x: x[1])
        path_sampah = nx.shortest_path(G, user_node, s_near_user, weight="length")
        coords_sampah = [(G.nodes[n]["y"], G.nodes[n]["x"]) for n in path_sampah]
        folium.PolyLine(coords_sampah, color="blue", weight=3, tooltip="Jalur ke Tempat Sampah Harian").add_to(m)

        waktu_harian = jarak_s / (5000 / 60)
        st.sidebar.markdown(f"""
        ### ♻️ Jalur ke Tempat Sampah Harian
        - 📏 Jarak: `{jarak_s:.1f} meter`
        - 🕒 Estimasi waktu: `{waktu_harian:.1f} menit`
        """)

        sampah_sorted = sorted(harian_to_user, key=lambda x: x[1])[:3]
        st.sidebar.markdown("### 📂 3 Tempat Sampah Terdekat:")
        for i, (node_id, jrk) in enumerate(sampah_sorted, start=1):
            y, x = G.nodes[node_id]["y"], G.nodes[node_id]["x"]
            waktu_menit = jrk / (5000/60)
            st.sidebar.markdown(f"- {i}. ({y:.5f}, {x:.5f}) - {jrk:.0f} m ({waktu_menit:.1f} menit)")

    except:
        st.warning("⚠️ Gagal hitung jalur dari lokasi Anda.")

    m.save("map.html")
    with open("map.html", "r", encoding="utf-8") as f:
        html_map = f.read()
    st_html(html_map, height=650, scrolling=True)

# Sidebar legenda
st.sidebar.markdown("""---  
**Legenda**  
🔵 Lokasi Anda  
🟢 TPS Nyata  
⚪ Tempat Sampah Harian  
🟠 Jalur Harian ke TPS  
🔴 Jalur Anda ke TPS  
🔵 Jalur ke Sampah Harian
""")