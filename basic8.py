from google import genai
import os
import streamlit as st
from pathlib import Path
import base64
import io
from PIL import Image
from dotenv import load_dotenv
from google.genai import types
from google.genai import errors
import fitz  # PyMuPDF
import time

# Load environment variables
load_dotenv()

# Initialize working client
working_client = None
api_key = st.secrets.get("GOOGLE_API_KEY", "")
api_key1 = st.secrets.get("GOOGLE_API_KEY1", "")
api_key2 = st.secrets.get("GOOGLE_API_KEY2", "")
api_key3 = st.secrets.get("GOOGLE_API_KEY3", "")
api_key4 = st.secrets.get("GOOGLE_API_KEY4", "")

# Test API keys
for key in [api_key, api_key1, api_key2, api_key3, api_key4]:
    try:
        client = genai.Client(api_key=key)
        client.models.list()
        working_client = client
        print("FFFFFFFFFFFFFFF")
        break
    except Exception as e:
        continue

# --- SEHEMU MPYA YA KUOKOA RAM ---

@st.cache_resource
def load_pdf_data():
    data_folder = Path("./data2")
    processed_data = []
    
    for pdf_filepath in data_folder.glob("*.pdf"):
        try:
            doc = fitz.open(pdf_filepath)
            for page_num in range(len(doc)):
                page = doc[page_num]
                # Tunahifadhi TEXT tu ili kutafuta haraka bila kula RAM
                processed_data.append({
                    "pdf_name": pdf_filepath.name,
                    "page_number": page_num + 1,
                    "page_text": page.get_text("text"),
                    "filepath": str(pdf_filepath) # Tunahifadhi path ili kuipata picha baadaye
                })
            doc.close()
        except Exception as e:
            st.error(f"❌ {pdf_filepath.name}: {str(e)}")
    return processed_data

def get_page_image(filepath, page_num):
    doc = fitz.open(filepath)
    page = doc[page_num - 1] # fitz huanza na 0
    pix = page.get_pixmap()
    img_bytes = pix.tobytes("png")
    doc.close() # Funga doc baada ya kupata picha
    return Image.open(io.BytesIO(img_bytes))

# Ite hivi:
pdf_pages_data = load_pdf_data()

# --- MWISHO WA SEHEMU YA RAM OPTIMIZATION ---

def get_pdf_part_on_demand(filepath, page_num):
    """Inatengeneza types.Part ya Gemini pale inapohitajika tu"""
    doc = fitz.open(filepath)
    temp_pdf = fitz.open()
    temp_pdf.insert_pdf(doc, from_page=page_num-1, to_page=page_num-1)
    temp_pdf_bytes = temp_pdf.write()
    temp_pdf.close()
    doc.close()
    return types.Part.from_bytes(data=temp_pdf_bytes, mime_type="application/pdf")

def process_pdf_and_query(user_prompt):
    relevant_pages = get_relevant_pages_smart(user_prompt)
    
    if not relevant_pages:
        return "Samahani, sijaona kurasa zinazohusiana na swali lako kwenye mafaili yako."
    
    contents = [user_prompt]
    # Badala ya kutumia p.data (ambayo haipo tena kwenye RAM), tunatengeneza on-demand
    for p in relevant_pages[:2]: # Tunatuma kurasa 2 tu ili API isifeli
        pdf_part = get_pdf_part_on_demand(p["filepath"], p["page_number"])
        contents.append(pdf_part)

    response_text = None
    for key in [api_key, api_key1, api_key2, api_key3, api_key4]:
        try:
            working_client = genai.Client(api_key=key)
            response = working_client.models.generate_content(
                model="gemini-1.5-flash", # Nimetumia 1.5 kwasababu 2.5 haipo bado
                contents=contents,
            )
            response_text = response.text
            break
        except Exception as e:
            continue
        
    return response_text

@st.cache_data(ttl=3600, show_spinner=False)
def get_relevant_pages_smart(user_prompt):
    relevant_pages = []
    
    if not pdf_pages_data:
        return []
    
    prompt_keywords = [word.lower() for word in user_prompt.lower().split() if len(word) > 3]
    if not prompt_keywords:
        prompt_keywords = [user_prompt.lower()]
    
    for page_data in pdf_pages_data:
        text = page_data["page_text"].lower()
        match_count = sum(1 for keyword in prompt_keywords if keyword in text)
        
        if match_count > 0:
            context = ""
            lines = page_data["page_text"].split('\n')
            for i, line in enumerate(lines):
                if any(keyword in line.lower() for keyword in prompt_keywords):
                    context = ' '.join(lines[max(0, i-2):min(len(lines), i+3)])
                    break
            
            relevant_pages.append({
                "pdf_name": page_data["pdf_name"],
                "page_number": page_data["page_number"],
                "filepath": page_data["filepath"],
                "page_text": page_data["page_text"],
                "match_score": match_count,
                "matched_words": [k for k in prompt_keywords if k in text],
                "context": context[:300] + "..." if len(context) > 300 else context
            })
    
    relevant_pages.sort(key=lambda x: x["match_score"], reverse=True)
    return relevant_pages

def safe_api_call(contents, max_retries=2):
    for key in [api_key, api_key1, api_key2, api_key3]:
        for attempt in range(max_retries):
            try:
                client = genai.Client(api_key=key)
                response = client.models.generate_content(
                    model="gemini-1.5-flash",
                    contents=contents,
                    config=types.GenerateContentConfig(max_output_tokens=500, temperature=0.3)
                )
                return response.text, True
            except:
                continue
    return None, False

def process_pdf_with_suggested_pages(user_prompt):
    relevant_pages = get_relevant_pages_smart(user_prompt)
    if not relevant_pages:
        return "Samahani, sijaona kurasa zinazohusiana na swali lako.", [], []
    
    selected_pages = relevant_pages
    response_text = ""
    api_used = False
    
    if working_client and len(selected_pages) >= 1:
        try:
            # Pata data ya ukurasa wa kwanza tu kutuma kwa Gemini kwasababu ya limit
            pdf_part = get_pdf_part_on_demand(selected_pages[0]["filepath"], selected_pages[0]["page_number"])
            contents = [f"Swali la mtumiaji: {user_prompt}\n\nMuktadha: {selected_pages[0].get('context', '')[:500]}", pdf_part]
            
            api_response, api_success = safe_api_call(contents)
            if api_success:
                response_text = f"**🤖 Majibu (Gemini API):**\n\n{api_response}"
                api_used = True
        except: pass

    if not api_used:
        response_text = "**ℹ️ Taarifa (Bila API):**\n\n"
        for page in selected_pages[:3]: # Onyesha 3 za kwanza tu kuzuia msongamano
            response_text += f"**📄 Ukurasa {page['page_number']} wa {page['pdf_name']}:**\n"
            response_text += f"**Muktadha:** {page['context']}\n\n"
    
    return response_text, selected_pages, []

# Streamlit UI
st.set_page_config(page_title="Mfumo wa Mwongozo wa Mtumiaji wa (DHMS)", page_icon="📄", layout="wide")

with st.sidebar:
    st.title("⚙️ Chagua Njia ya Utafutaji")
    search_mode = st.radio("**Chagua aina ya utafutaji:**", ["text_explanation", "image_search"],
        format_func=lambda x: {"text_explanation": "📝 Taarifa ya maelezo", "image_search": "📸 Taarifa ya Picha"}[x])

st.subheader("📄 Mfumo wa Mwongozo wa Mtumiaji wa (DHMS)")

col1, col2 = st.columns([4, 1])
with col1:
    prompt = st.text_input("", placeholder="Andika hitajio lako hapa...", label_visibility="collapsed")
with col2:
    get_images = st.checkbox("📸 Pata picha", value=(search_mode == "image_search"))

col_btn1, col_btn2, col_btn3 = st.columns(3)
with col_btn1:
    search_btn = st.button("🔍 Tafuta Taarifa", use_container_width=True)
with col_btn2:
    if st.button("🗑️ Futa Yote", use_container_width=True): st.rerun()
with col_btn3:
    preview_btn = st.button("👁️ Angalia Kurasa Zote", use_container_width=True)

if preview_btn:
    st.markdown("### 📚 Kurasa Zote Zilizosomwa")
    for page in pdf_pages_data:
        with st.expander(f"📖 {page['pdf_name']} - Ukurasa {page['page_number']}"):
            img = get_page_image(page["filepath"], page["page_number"])
            st.image(img, use_container_width=True)

if search_btn and prompt:
    with st.spinner("🔍 Inatafuta..."):
        if search_mode == "text_explanation":
            st.markdown("#### 📝 Taarifa ya maelezo")
            res = process_pdf_and_query(prompt)
            st.info(res)
        elif search_mode == "image_search" or get_images:
            res_text, selected, _ = process_pdf_with_suggested_pages(prompt)
            st.markdown(res_text)
            for p in selected[:3]:
                img = get_page_image(p["filepath"], p["page_number"])
                st.image(img, caption=f"Ukurasa {p['page_number']} - {p['pdf_name']}", use_container_width=True)

st.markdown("---")
st.markdown("<div style='text-align: center'><small>📊 Mfumo wa Mwongozo wa Mtumiaji wa (DHMS)</div>", unsafe_allow_html=True)