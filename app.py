import streamlit as st
import requests

# Replace with your FastAPI server URL
API_BASE_URL = "https://chatbot-5-dn6z.onrender.com"  # or public IP/domain

st.set_page_config(page_title="PDF QA System", layout="centered")

st.title("📄 Ask Questions from Your PDF Files")

# === Upload PDFs ===
st.header("1️⃣ Upload your PDF files")

uploaded_files = st.file_uploader(
    "Upload one or more PDFs", type=["pdf"], accept_multiple_files=True
)

if uploaded_files and st.button("Upload PDFs"):
    with st.spinner("Uploading and processing..."):
        files = [("files", (f.name, f, "application/pdf")) for f in uploaded_files]
        try:
            res = requests.post(f"{API_BASE_URL}/upload_pdfs", files=files)
            if res.status_code == 200:
                st.success("✅ PDF(s) uploaded and processed successfully.")
            else:
                st.error(f"❌ Error: {res.json()['detail']}")
        except Exception as e:
            st.error(f"Connection error: {e}")

# === Ask Question ===
st.header("2️⃣ Ask a question based on uploaded PDFs")

user_question = st.text_input("Enter your question")

if st.button("Ask"):
    if not user_question.strip():
        st.warning("Please enter a valid question.")
    else:
        with st.spinner("Fetching answer..."):
            try:
                res = requests.post(
                    f"{API_BASE_URL}/ask_question",
                    json={"question": user_question}
                )
                if res.status_code == 200:
                    st.success("🧠 Answer:")
                    st.markdown(f"**{res.json()['answer']}**")
                else:
                    st.error(f"❌ Error: {res.json()['detail']}")
            except Exception as e:
                st.error(f"Connection error: {e}")
