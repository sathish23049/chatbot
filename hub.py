from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from PyPDF2 import PdfReader
from openai import OpenAI
from langchain.prompts import PromptTemplate
from dotenv import load_dotenv
import os
import shutil

# Load environment variables
load_dotenv()
api_key = os.getenv("sambanova-api-key")

if not api_key:
    raise ValueError("Missing 'sambanova-api-key' in .env")

# Create uploads directory if it doesn't exist
UPLOAD_FOLDER = "./uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global text context (in-memory)
DOCUMENT_CONTEXT = ""

# === Upload PDF Endpoint ===
@app.post("/upload_pdfs")
async def upload_pdfs(files: list[UploadFile] = File(...)):
    global DOCUMENT_CONTEXT
    text = ""

    for file in files:
        file_location = os.path.join(UPLOAD_FOLDER, file.filename)

        # Save file to local disk
        try:
            with open(file_location, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to save file: {file.filename}")

        # Re-open the saved file to read text
        try:
            with open(file_location, "rb") as f:
                pdf_reader = PdfReader(f)
                for page in pdf_reader.pages:
                    text += page.extract_text() or ""
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error reading PDF: {file.filename}")

    if not text.strip():
        raise HTTPException(status_code=400, detail="No readable text in uploaded PDFs.")

    DOCUMENT_CONTEXT = text  # Save to in-memory context
    return JSONResponse(content={"message": "PDFs uploaded, saved locally, and content extracted."})

# === Ask Question Endpoint ===
@app.post("/ask_question")
async def ask_question(question: dict):
    global DOCUMENT_CONTEXT
    user_question = question.get("question")

    if not user_question:
        raise HTTPException(status_code=400, detail="Missing 'question' field.")

    # If in-memory context is empty, try loading all PDF files from uploads folder
    if not DOCUMENT_CONTEXT:
        pdf_files = [f for f in os.listdir(UPLOAD_FOLDER) if f.lower().endswith(".pdf")]
        if not pdf_files:
            raise HTTPException(status_code=400, detail="No uploaded PDFs found in local storage.")

        combined_text = ""
        for filename in pdf_files:
            file_path = os.path.join(UPLOAD_FOLDER, filename)
            try:
                with open(file_path, "rb") as f:
                    pdf_reader = PdfReader(f)
                    for page in pdf_reader.pages:
                        combined_text += page.extract_text() or ""
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Failed to read {filename}: {str(e)}")

        if not combined_text.strip():
            raise HTTPException(status_code=400, detail="No readable text found in uploaded PDFs.")

        DOCUMENT_CONTEXT = combined_text  # Store all combined PDF text in memory

    # Prompt construction
    prompt_template = """
    Answer the question as accurately as possible based on the provided context.
    If the answer is not in the context, respond with: "Answer is not available in the context."

    Context:
    {context}

    Question:
    {question}

    Answer:
    """
    prompt = PromptTemplate(template=prompt_template, input_variables=["context", "question"])
    formatted_prompt = prompt.format(context=DOCUMENT_CONTEXT, question=user_question)

    # Sambanova API call
    try:
        client = OpenAI(
            api_key=api_key,
            base_url="https://api.sambanova.ai/v1"
        )

        response = client.chat.completions.create(
            model="Llama-4-Maverick-17B-128E-Instruct",
            messages=[{
                "role": "user",
                "content": [{"type": "text", "text": formatted_prompt}]
            }],
            temperature=0.1,
            top_p=0.1
        )

        answer = response.choices[0].message.content
        return JSONResponse(content={"answer": answer})

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sambanova API error: {str(e)}")
    

import streamlit as st
import requests

# Replace with your FastAPI server URL
API_BASE_URL = "http://localhost:8000"  # or public IP/domain

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


