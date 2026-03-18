import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import plotly.express as px
from PIL import Image
import io
import os
import matplotlib.patches as mpatches

# ----------------------------
# CONFIG
# ----------------------------
st.set_page_config(page_title="ENI NSV Dashboard", layout="wide")

# ----------------------------
# LOAD DATA
# ----------------------------
@st.cache_data
def load_data():
    file = "nsv_data.xlsx"

    sheets = {
        "LHS_Fast": pd.read_excel(file, sheet_name="LHS_Fast"),
        "LHS_Slow": pd.read_excel(file, sheet_name="LHS_Slow"),
        "RHS_Fast": pd.read_excel(file, sheet_name="RHS_Fast"),
        "RHS_Slow": pd.read_excel(file, sheet_name="RHS_Slow"),
    }

    for k in sheets:
        sheets[k].columns = sheets[k].columns.str.strip()

    return sheets

data = load_data()
lanes = list(data.keys())
df_base = data["LHS_Fast"]

# ----------------------------
# LOGO SAFE LOAD
# ----------------------------
col1, col2 = st.columns([1,5])

if os.path.exists("logo.png"):
    logo = Image.open("logo.png")
    col1.image(logo, width=180)
else:
    col1.write("ENI")

col2.markdown("<h1>Road Maintenance Dashboard</h1>", unsafe_allow_html=True)

st.markdown("---")

# ----------------------------
# SESSION STATE
# ----------------------------
for key in ["manual_sections", "index_sections", "custom_sections", "custom_rules"]:
    if key not in st.session_state:
        st.session_state[key] = []

# ----------------------------
# COST SETTINGS
# ----------------------------
st.sidebar.header("💰 Cost Settings")

cost_dict = {
    "Overlay": st.sidebar.number_input("Overlay ₹/km", 2500000, key="c1"),
    "Mill & Overlay": st.sidebar.number_input("Mill & Overlay ₹/km", 3000000, key="c2"),
    "Patch": st.sidebar.number_input("Patch ₹/km", 500000, key="c3"),
    "Rehabilitation": st.sidebar.number_input("Rehabilitation ₹/km", 3500000, key="c4"),
    "Crack Seal": st.sidebar.number_input("Crack Seal ₹/km", 300000, key="c5"),
    "Slurry Seal / Micro Surfacing": st.sidebar.number_input("Slurry ₹/km", 800000, key="c6")
}

# ----------------------------
# PCI COLOR
# ----------------------------
def pci_gradient(pci):
    ratio = pci / 100
    red = int(255 * (1 - ratio))
    green = int(255 * ratio)
    return f'#{red:02x}{green:02x}00'

# ----------------------------
# PATTERN
# ----------------------------
pattern_dict = {
    "Overlay": "////",
    "Mill & Overlay": "xxxx",
    "Patch": "....",
    "Rehabilitation": "++++",
    "Crack Seal": "----",
    "Slurry Seal / Micro Surfacing": "oooo"
}

# ----------------------------
# FLOWCHART LOGIC
# ----------------------------
def final_recommendation(iri, traffic, pci):

    if traffic < 450:
        iri_th = 3.5
    elif traffic < 1500:
        iri_th = 3.3
    elif traffic < 6000:
        iri_th = 3.0
    else:
        iri_th = 2.55

    if iri > iri_th:
        return "Rehabilitation"

    if pci >= 90:
        return "Do Nothing"
    elif pci >= 80:
        return "Crack Seal"
    elif pci >= 60:
        return "Slurry Seal / Micro Surfacing"
    else:
        return "Rehabilitation"

# ----------------------------
# MODE
# ----------------------------
mode = st.radio(
    "Select Mode",
    ["Manual Planning", "Index-Based Recommendation", "Custom Rule-Based"],
    horizontal=True
)

# =========================================================
# 🔷 CHART
# =========================================================
st.subheader("📊 Condition Profile")

fig = px.line()

if mode == "Custom Rule-Based":

    cols = list(df_base.columns)

    c1, c2, c3 = st.columns(3)

    x_axis = c1.selectbox("X Axis", cols, key="x_axis")
    y_axis = c2.selectbox("Y Axis", cols, key="y_axis")
    selected_lanes = c3.multiselect("Lanes", lanes, default=lanes, key="lane_sel")

    for lane in selected_lanes:
        fig.add_scatter(x=data[lane][x_axis], y=data[lane][y_axis], name=lane)

    fig.update_layout(xaxis_title=x_axis, yaxis_title=y_axis)

else:
    y = "IRI" if mode == "Manual Planning" else "PCI"

    for lane in lanes:
        fig.add_scatter(x=data[lane]["Chainage"], y=data[lane][y], name=lane)

    fig.update_layout(xaxis_title="Chainage (km)", yaxis_title=y)

st.plotly_chart(fig, use_container_width=True)

# =========================================================
# 🔷 CUSTOM RULES
# =========================================================
if mode == "Custom Rule-Based":

    st.subheader("⚙️ Define Rules")

    c1, c2, c3 = st.columns(3)

    param = c1.selectbox("Parameter", list(df_base.columns), key="rule_param")
    threshold = c2.number_input("Threshold", key="rule_th")
    treatment = c3.selectbox("Treatment", list(pattern_dict.keys()), key="rule_treat")

    if st.button("Add Rule"):
        st.session_state.custom_rules.append({
            "param": param,
            "threshold": threshold,
            "treatment": treatment
        })

    st.write("Active Rules:", st.session_state.custom_rules)

# =========================================================
# 🔷 ADD SECTION
# =========================================================
st.subheader("➕ Add Section")

c1, c2, c3 = st.columns(3)

start, end = c1.slider("Chainage", 0.0, float(df_base["Chainage"].max()), (0.0, 0.5), key="sec_slider")
treatment = c2.selectbox("Treatment", list(pattern_dict.keys()), key="sec_treat")
lanes_sel = c3.multiselect("Lanes", lanes, default=[lanes[0]], key="sec_lane")

if st.button("Add Section Button"):
    sec = {"start": start, "end": end, "treatment": treatment, "lanes": lanes_sel}

    if mode == "Manual Planning":
        st.session_state.manual_sections.append(sec)
    elif mode == "Index-Based Recommendation":
        st.session_state.index_sections.append(sec)
    else:
        st.session_state.custom_sections.append(sec)

# =========================================================
# 🔷 SECTION LOGIC
# =========================================================
sections = []

if mode == "Manual Planning":
    sections = st.session_state.manual_sections

elif mode == "Index-Based Recommendation":

    for lane in lanes:
        df_lane = data[lane]

        for i in range(len(df_lane)):
            rec = final_recommendation(
                df_lane["IRI"][i],
                df_lane["Traffic"][i],
                df_lane["PCI"][i]
            )

            if rec != "Do Nothing":
                sections.append({
                    "start": df_lane["Chainage"][i],
                    "end": df_lane["Chainage"][i] + 0.01,
                    "treatment": rec,
                    "lanes": [lane]
                })

    sections += st.session_state.index_sections

else:

    for lane in lanes:
        df_lane = data[lane]

        for i in range(len(df_lane)):
            for rule in st.session_state.custom_rules:
                if df_lane.iloc[i][rule["param"]] >= rule["threshold"]:
                    sections.append({
                        "start": df_lane["Chainage"][i],
                        "end": df_lane["Chainage"][i] + 0.01,
                        "treatment": rule["treatment"],
                        "lanes": [lane]
                    })
                    break

    sections += st.session_state.custom_sections

# =========================================================
# 🔷 ROAD MAP
# =========================================================
st.subheader("🛣️ Road Condition View")

fig, ax = plt.subplots(figsize=(14,5))
positions = {lane: i for i, lane in enumerate(lanes[::-1])}

for lane in lanes:
    df_lane = data[lane]

    for i in range(len(df_lane)):
        chain = df_lane["Chainage"][i]

        if mode == "Manual Planning":
            color = "#e74c3c" if df_lane["IRI"][i] > 3.3 else "#2ecc71"
        else:
            color = pci_gradient(df_lane["PCI"][i])

        hatch = None

        for sec in sections:
            if sec["start"] <= chain <= sec["end"] and lane in sec["lanes"]:
                hatch = pattern_dict.get(sec["treatment"])

        ax.barh(positions[lane], 0.01, left=chain, color=color, hatch=hatch, edgecolor="black")

ax.set_yticks(list(positions.values()))
ax.set_yticklabels(list(positions.keys()))
ax.set_xlabel("Chainage (km)")

st.pyplot(fig)

# =========================================================
# 🔷 LEGENDS
# =========================================================
st.subheader("🎨 Legend")

col1, col2 = st.columns(2)

with col1:
    if mode == "Manual Planning":
        st.markdown("🟢 Good (IRI ≤ 3.3)\n\n🔴 Bad (IRI > 3.3)")
    else:
        st.markdown("PCI Gradient:\n\n🔴 0 → 🟢 100")

with col2:
    for k, v in pattern_dict.items():
        st.markdown(f"{v} → {k}")

# =========================================================
# 🔷 COST TABLE + EXPORT
# =========================================================
st.subheader("📋 Maintenance Plan & Cost")

rows = []
total_cost = 0

for sec in sections:
    length = sec["end"] - sec["start"]
    lane_count = len(sec["lanes"])
    rate = cost_dict.get(sec["treatment"], 0)

    cost = length * rate * lane_count
    total_cost += cost

    rows.append({
        "Start": sec["start"],
        "End": sec["end"],
        "Length (km)": round(length,3),
        "Treatment": sec["treatment"],
        "Lanes": ", ".join(sec["lanes"]),
        "Cost (₹)": int(cost)
    })

if rows:
    df_plan = pd.DataFrame(rows)
    st.dataframe(df_plan)

    st.success(f"💰 Total Cost: ₹ {int(total_cost):,}")

    buffer = io.BytesIO()
    df_plan.to_excel(buffer, index=False, engine='openpyxl')

    st.download_button(
        "⬇️ Download Excel",
        buffer.getvalue(),
        "Maintenance_Plan.xlsx"
    )
