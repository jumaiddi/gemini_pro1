import streamlit as st
import os
from pathlib import Path
import PyPDF2  # For text extraction
from sentence_transformers import SentenceTransformer  # For creating embeddings
import chromadb
from chromadb.config import Settings
from google import genai


# 1. Initialize Embedding Model & Chroma Client
@st.cache_resource
def init_components():
    # Model to convert text to vectors
    embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
    # Persistent Chroma client (stores data locally in `./chroma_db`)
    chroma_client = chromadb.PersistentClient(path="./chroma_db")
    return embedding_model, chroma_client

# 2. Process PDFs and Populate Chroma DB (Run once)
def build_knowledge_base(pdf_folder_path, collection_name="azania_members"):
    embedding_model, chroma_client = init_components()
    
    # Get or create a collection
    collection = chroma_client.get_or_create_collection(
        name=collection_name,
        metadata={"hnsw:space": "cosine"} # Distance metric
    )
    
    all_texts = []
    all_embeddings = []
    all_metadatas = []
    all_ids = []
    
    data_folder = Path(pdf_folder_path)
    pdf_files = list(data_folder.glob("*.pdf"))
    
    for pdf_path in pdf_files:
        # Extract text from PDF
        with open(pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            pdf_text = ""
            for page_num, page in enumerate(pdf_reader.pages):
                page_text = page.extract_text()
                if page_text:
                    pdf_text += f"\n--- Page {page_num+1} ---\n{page_text}"
        
        # Simple chunking: Split by paragraphs or fixed size
        chunks = [chunk for chunk in pdf_text.split('\n\n') if len(chunk) > 50]
        
        for i, chunk in enumerate(chunks):
            # Create embedding for the chunk
            embedding = embedding_model.encode(chunk).tolist()
            
            all_texts.append(chunk)
            all_embeddings.append(embedding)
            all_metadatas.append({"source": pdf_path.name, "chunk_id": i})
            all_ids.append(f"{pdf_path.stem}_chunk{i}")
    
    # Add all chunks to Chroma DB in one batch
    if all_texts:
        collection.add(
            documents=all_texts,
            embeddings=all_embeddings,
            metadatas=all_metadatas,
            ids=all_ids
        )
        st.success(f"✅ Knowledge base built with {len(all_texts)} text chunks from {len(pdf_files)} PDF(s).")
    return collection

# 3. New Query Function using RAG
def query_with_rag(user_prompt, collection, k_results=5):
    """Retrieves relevant context from Chroma DB and queries Gemini."""
    embedding_model, _ = init_components()
    
    # 3.1 Convert user question to a vector and search Chroma
    query_embedding = embedding_model.encode(user_prompt).tolist()
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=k_results,
        include=["documents", "metadatas", "distances"]
    )
    
    # 3.2 Format the retrieved context
    context_chunks = results['documents'][0]
    sources = results['metadatas'][0]
    
    context = "\n\n---\n\n".join([
        f"[From: {src['source']}]\n{chunk}"
        for chunk, src in zip(context_chunks, sources)
    ])
    
    # 3.3 Create the enhanced prompt for Gemini
    rag_prompt = f"""You are a helpful assistant. Answer the user's question based *only* on the provided context. 
If the answer is not in the context, say so.

CONTEXT:
{context}

QUESTION:
{user_prompt}

ANSWER:"""
    
    # 3.4 Call Gemini with the concise prompt (reuse your API client logic)
    for key in [st.secrets["GOOGLE_API_KEY"], st.secrets["GOOGLE_API_KEY1"], st.secrets["GOOGLE_API_KEY2"]]:
        try:
            client = genai.Client(api_key=key)
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=rag_prompt,
            )
            return response.text
        except Exception as e:
            continue
    return "Error: Could not get a response from the AI model."

# --- Streamlit UI (Updated) ---
st.markdown("<h5>📄 Mfumo wa kupata taarifa za Wanachama wa Azania 2006</h5>", unsafe_allow_html=True)

# Initialize or load the knowledge base
embedding_model, chroma_client = init_components()
collection = chroma_client.get_or_create_collection(name="azania_members")

# Button to rebuild the knowledge base (optional, for admin)
if st.sidebar.button("Jenga Upya Msingi wa Maarifa kutoka PDFs"):
    with st.spinner("Inasoma PDF na kujenga msingi wa maarifa..."):
        collection = build_knowledge_base("./data", "azania_members")

st.markdown("###### Andika Hitajio Lako")
prompt = st.text_area("Andika hitajio lako", height=10, label_visibility="collapsed")

if st.button("Pata taarifa"):
    if not prompt:
        st.warning("Andika swali kabla ya kubonyeza 'Pata Jibu'.")
    else:
        with st.spinner("Inatafuta katika hati na kukusanya jibu..."):
            try:
                # Use the new RAG query function
                response_text = query_with_rag(prompt, collection)
                st.info(response_text)
            except Exception as e:
                st.error(f"Kosa limetokea: {e}")