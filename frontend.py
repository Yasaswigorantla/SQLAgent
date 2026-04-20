import streamlit as st
import requests
import pandas as pd


def format_attribute(attribute):
    if isinstance(attribute, dict):
        name = attribute.get("name", "")
        markers = []

        if attribute.get("primary_key") or attribute.get("part_of_composite_pk"):
            markers.append("PK")
        if attribute.get("foreign_key"):
            markers.append("FK")

        marker_text = f" ({', '.join(markers)})" if markers else ""
        return f"{name}{marker_text}"

    return str(attribute)

# 🔥 PAGE CONFIG
st.set_page_config(page_title="AI DB Agent", layout="wide")

# 🔥 SESSION STATE (IMPORTANT - prevents reset)
if "data" not in st.session_state:
    st.session_state.data = None

if "input_text" not in st.session_state:
    st.session_state.input_text = ""

# 🔥 CUSTOM CSS (IMPROVED COLORS)
st.markdown("""
<style>
.main {
    background-color: #0e1117;
}
.block-container {
    padding-top: 2rem;
}

/* Cards */
.card {
    padding: 15px;
    border-radius: 12px;
    background-color: #262730;
    color: #ffffff;
    margin-bottom: 15px;
    box-shadow: 0px 0px 8px rgba(0,0,0,0.3);
}

/* Titles */
.title {
    font-size: 32px;
    font-weight: bold;
    color: #ffffff;
}

.subtitle {
    color: #bbbbbb;
}
</style>
""", unsafe_allow_html=True)

# 🔥 SIDEBAR
st.sidebar.title("⚡ AI DB Agent")
mode = st.sidebar.radio("Input Mode", ["Dataset", "Manual"])

# 🔹 LOAD DATASET
df = pd.read_csv("dataset.csv")

# 🔥 HEADER
st.markdown('<p class="title">🤖 AI Database Design Agent</p>', unsafe_allow_html=True)
st.markdown('<p class="subtitle">Convert ideas → Schema → SQL → ER Diagram</p>', unsafe_allow_html=True)

# 🔹 INPUT
if mode == "Dataset":
    text = st.selectbox("📂 Choose Example", df["Description"])
else:
    text = st.text_area("✍️ Describe your system", height=120)

# 🔥 GENERATE BUTTON
if st.button("🚀 Generate"):

    with st.spinner("Thinking like a database architect... 🧠"):

        res = requests.post(
            "http://127.0.0.1:8000/generate",
            json={"text": text}
        )

        try:
            data = res.json()
        except:
            st.error("Backend error")
            st.text(res.text)
            st.stop()

    if data.get("error"):
        st.error(data["error"])
    else:
        st.session_state.data = data
        st.session_state.input_text = text

# 🔥 DISPLAY OUTPUT (PERSISTENT)
if st.session_state.data:

    data = st.session_state.data
    text = st.session_state.input_text

    st.success("Schema Generated Successfully!")

    # 🔥 TABS
    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs(
        ["📊 Schema", "🔗 Relationships", "🧾 SQL", "📐 ER Diagram", "📈 Evaluation", "Explanation", "Suggestions"]
    )

    # 🔹 SCHEMA TAB
    with tab1:
        st.subheader("Entities")

        cols = st.columns(3)
        for i, table in enumerate(data["schema"]):
            attribute_lines = "<br>".join(
                format_attribute(attribute) for attribute in table["attributes"]
            )
            with cols[i % 3]:
                st.markdown(f"""
                <div class="card">
                <h4>{table['name']}</h4>
                {attribute_lines}
                </div>
                """, unsafe_allow_html=True)

    # 🔹 RELATIONSHIPS TAB
    with tab2:
        st.subheader("Relationships")

        for rel in data["relationships"]:
            st.markdown(f"""
            <div class="card">
            {rel['from']} ➝ {rel['to']} ({rel['type']})
            </div>
            """, unsafe_allow_html=True)

    # 🔹 SQL TAB
    with tab3:
        st.subheader("SQL Output")
        st.code(data["sql"])

        st.download_button(
            "⬇ Download SQL",
            data=data["sql"],
            file_name="schema.sql"
        )

    # 🔹 ER DIAGRAM TAB
    with tab4:
        st.subheader("ER Diagram")
        st.image(data["er_diagram"])

    # 🔹 EVALUATION TAB
    with tab5:
        st.subheader("Evaluation")

        generated_entities = [t["name"] for t in data["schema"]]

        expected_row = df[df["Description"] == text]

        if not expected_row.empty:
            expected_entities = expected_row.iloc[0]["Expected_Entities"].split("|")

            gen_set = set(generated_entities)
            exp_set = set(expected_entities)

            correct = len(gen_set.intersection(exp_set))
            total = len(exp_set)

            accuracy = (correct / total) * 100 if total > 0 else 0

            st.markdown(f"""
            <div class="card">
            <b>Expected:</b> {expected_entities} <br><br>
            <b>Generated:</b> {generated_entities}
            </div>
            """, unsafe_allow_html=True)

            st.metric("Accuracy", f"{round(accuracy,2)}%")
        else:
            st.info("No evaluation data available for this input")
    with tab6:
        st.subheader("Design Explanation")
        st.write(data.get("explanation", "No explanation"))
    with tab7:
        st.subheader("Future Improvements")

        for s in data.get("suggestions", []):
            st.markdown(f"• {s}")
