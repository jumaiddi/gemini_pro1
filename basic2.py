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

load_dotenv()
working_client = None
api_key = st.secrets["GOOGLE_API_KEY"]
api_key1 = st.secrets["GOOGLE_API_KEY1"]
api_key2 = st.secrets["GOOGLE_API_KEY2"]
for key in [api_key, api_key1, api_key2]:
    try:
        client = genai.Client(api_key=key)
        client.models.list()
        working_client = client
        break
    except errors.APIError as e:
        continue

data_folder = Path("./data")
pdf_pages_data = []  # Hifadhi data ya kila ukurasa tofauti

# Kusoma PDF na kugawa kwa kurasa
for pdf_filepath in data_folder.glob("*.pdf"):
    try:
        # Kufungua PDF na kugawa kwa kurasa
        doc = fitz.open(pdf_filepath)
        pdf_name = pdf_filepath.name
        
        for page_num in range(len(doc)):
            # Kuchukua ukurasa wa PDF kama picha
            page = doc[page_num]
            pix = page.get_pixmap()
            img_bytes = pix.tobytes("png")
            
            # Kugeuza kuwa PIL Image
            pil_image = Image.open(io.BytesIO(img_bytes))
            
            # Kukamilisha ukurasa wa PDF kama data ya binary
            temp_pdf = fitz.open()
            temp_pdf.insert_pdf(doc, from_page=page_num, to_page=page_num)
            temp_pdf_bytes = temp_pdf.write()
            temp_pdf.close()
            
            # Hifadhi data ya kila ukurasa
            pdf_page = types.Part.from_bytes(
                data=temp_pdf_bytes,
                mime_type="application/pdf"
            )
            
            pdf_pages_data.append({
                "pdf_name": pdf_name,
                "page_number": page_num + 1,
                "pdf_data": pdf_page,
                "image": pil_image,
                "full_image_bytes": img_bytes,
                "page_text": page.get_text()  # Hifadhi text ya ukurasa
            })
        
        doc.close()
        print(f"Nimesoma faili kwa mafanikio: {pdf_filepath.name} - Kurasa: {len(pdf_pages_data)}")
        
    except Exception as e:
        print(f"Kosa katika kusoma {pdf_filepath.name}: {str(e)}")

# NAZIA MPYA: Tumia text-based search kwanza, halafu tumia API kwa kurasa chache tu
@st.cache_data(ttl=3600)  # Cache kwa saa 1
def get_relevant_pages_smart(user_prompt):
    """Tumia text-based search kwanza, halafu Gemini kwa verification"""
    relevant_pages = []
    print("CCCCCCCCCCCCCC")
    # STEP 1: Text-based search (bila API)
    for page_data in pdf_pages_data:
        text = page_data["page_text"].lower()
        print("QQQQQQQQQQQQQ ",text)
        prompt_words = user_prompt.lower().split()
        
        # Angalia keywords
        match_count = 0
        for word in prompt_words:
            if len(word) > 3 and word in text:  # Maneno marefu tu
                match_count += 1
        
        # Ikiwa angalau neno 1 limepatikana
        if match_count > 0:
            relevant_pages.append({
                "pdf_name": page_data["pdf_name"],
                "page_number": page_data["page_number"],
                "data": page_data["pdf_data"],
                "image": page_data["image"],
                "page_text": page_data["page_text"],
                "match_score": match_count,
                "description": f"Text match: {match_count} keywords"
            })
    
    # Sort by match score
    relevant_pages.sort(key=lambda x: x["match_score"], reverse=True)
    
    # Chukua kurasa 3 tu zenye score kubwa
    top_pages = relevant_pages[:3]
    
    # STEP 2: Tumia API kwa verification ya kurasa chache tu
    if top_pages:
        for key in [api_key, api_key1, api_key2]:
            try:
                client = genai.Client(api_key=key)
                working_client = client
                
                print(f"✅ API key inatumika kwa verification")
                
                verified_pages = []
                
                # Tumia API kwa kurasa 3 tu
                for i, page in enumerate(top_pages[:3]):  # 3 tu!
                    try:
                        # Weka delay kati ya requests
                        if i > 0:
                            time.sleep(1)
                        
                        # 1. Check relevance
                        response = working_client.models.generate_content(
                            model="gemini-2.5-flash",  # Tumia 1.5-flash (quota kubwa)
                            contents=[
                                f"User prompt: {user_prompt}\n\n"
                                f"Is this page relevant? Answer 'YES' or 'NO' only.",
                                page["data"]
                            ]
                        )
                        print("KKKKKKKKKKKKKKKKK")
                        if "YES" in response.text.upper:
                            print("AAAAAAAAAAAAAAAAA")
                            # 2. Get description
                            desc_response = working_client.models.generate_content(
                                model="gemini-2.5-flash",
                                contents=[
                                    "Describe this page in 2-3 words:",
                                    page["data"]
                                ]
                            )
                            
                            page["description"] = desc_response.text.strip()
                            page["verified"] = True
                            verified_pages.append(page)
                            print(f"  ✓ Ukurasa {page['page_number']} imethibitishwa")
                        
                    except Exception as e:
                        print(f"  ✗ API error for page {page['page_number']}: {e}")
                        # Endelea na ukurasa ujao
                        continue
                
                # Ikiwa tumepata verified pages
                if verified_pages:
                    return verified_pages
                else:
                    # Rudi na top pages bila verification
                    return top_pages
                
            except Exception as e:
                print(f"Key failed: {e}")
                continue
    
    # Ikiwa hakuna kurasa zilizopatikana, rudi na kurasa 3 za kwanza
    if not relevant_pages and pdf_pages_data:
        return [{
            "pdf_name": pdf_pages_data[0]["pdf_name"],
            "page_number": pdf_pages_data[0]["page_number"],
            "data": pdf_pages_data[0]["pdf_data"],
            "image": pdf_pages_data[0]["image"],
            "description": "Ukurasa wa kwanza",
            "verified": False
        }]
    
    return relevant_pages[:5]  # Rudi na top 5 even without API verification

def process_pdf_with_suggested_pages(user_prompt):
    """Pata majibu kutoka kwenye kurasa zilizopendekezwa"""
    print("MMMMMMMMMMMMMMMMM  function one called")
    # Pata kurasa zinazohusiana (tumia smart version)
    relevant_pages = get_relevant_pages_smart(user_prompt)
    
    if not relevant_pages:
        return "Samahani, sijaona kurasa zinazohusiana na swali lako.", [], []
    
    # Ona kurasa zilizopatikana
    st.info(f"📄 Nimepata kurasa {len(relevant_pages)} zinazohusiana:")
    
    page_list = []
    for i, page in enumerate(relevant_pages):
        verified_mark = "✅" if page.get("verified", False) else "📄"
        page_list.append(f"{i+1}. {verified_mark} {page['pdf_name']} - Ukurasa {page['page_number']}: {page['description']}")
    
    st.write("\n".join(page_list))
    
    # Kuuliza mtumiaji kuchagua kurasa (au tumia zote)
    selected_pages = []
    if len(relevant_pages) > 1:
        st.write("### Chagua kurasa unazotaka:")
        
        cols = st.columns(3)
        selected_indices = []
        
        for i, page in enumerate(relevant_pages):
            with cols[i % 3]:
                if st.checkbox(
                    f"Ukurasa {page['page_number']}",
                    key=f"page_{i}",
                    value=True  # By default, zote zimechaguliwa
                ):
                    selected_indices.append(i)
        
        selected_pages = [relevant_pages[i] for i in selected_indices]
    else:
        selected_pages = relevant_pages
    
    if not selected_pages:
        return "Hujachagua kurasa yoyote. Tafadhali chagua angalau ukurasa mmoja.", [], []
    
    # Pata majibu kutoka kwenye kurasa zilizochaguliwa
    combined_response = ""
    all_page_images = []
    
    for page_meta in selected_pages:
        for key in [api_key, api_key1, api_key2]:
            try:
                client = genai.Client(api_key=key)
                working_client = client
                
                # Pata majibu kutoka kwenye ukurasa maalum
                response = working_client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=[
                        f"User prompt: {user_prompt}\n\n"
                        f"Answer based ONLY on this specific page {page_meta['page_number']} of {page_meta['pdf_name']}. "
                        f"Be concise and specific.",
                        page_meta["data"]
                    ]
                )
                
                combined_response += f"\n\n**📄 Ukurasa {page_meta['page_number']} wa {page_meta['pdf_name']}:**\n"
                combined_response += response.text
                
                # Hifadhi picha ya ukurasa
                all_page_images.append({
                    "image": page_meta["image"],
                    "page": page_meta["page_number"],
                    "filename": page_meta["pdf_name"],
                    "description": page_meta["description"]
                })
                
                break  # Ikiwa imefanikiwa, toka kwenye loop ya keys
                
            except Exception as e:
                print(f"Kosa katika kusoma ukurasa {page_meta['page_number']} na key: {e}")
                continue
    
    return combined_response, all_page_images, selected_pages

def extract_specific_images(prompt, selected_pages):
    """Toa picha maalum kutoka kwenye kurasa zilizochaguliwa"""
    specific_images = []
    
    for page_meta in selected_pages:
        try:
            # Extract picha kutoka kwenye ukurasa
            doc = fitz.open(stream=page_meta["data"].file_data, filetype="pdf")
            page = doc[0]  # Ukurasa wa kwanza tu kwa sababu tumegawanya PDF
            
            images = page.get_images()
            for img_index, img in enumerate(images[:2]):  # Chukua picha 2 tu kwa kila ukurasa
                xref = img[0]
                base_image = doc.extract_image(xref)
                image_bytes = base_image["image"]
                
                # Badilisha kuwa PIL Image
                pil_image = Image.open(io.BytesIO(image_bytes))
                
                # Angalia ikiwa picha inahusiana na prompt (text-based check)
                # Kwanza jaribu text-based check (bila API)
                should_use_api = False
                
                # Simple check: Ikiwa prompt ina maneno kama "picha", "photo", etc.
                image_keywords = ["picha", "photo", "sura", "passport", "sahihi", "signature", "mchoro"]
                prompt_lower = prompt.lower()
                
                for keyword in image_keywords:
                    if keyword in prompt_lower:
                        should_use_api = True
                        break
                
                # Tumia API ikiwa inahitajika
                if should_use_api:
                    for key in [api_key, api_key1, api_key2]:
                        try:
                            client = genai.Client(api_key=key)
                            working_client = client
                            
                            buffered = io.BytesIO()
                            pil_image.save(buffered, format="PNG")
                            img_base64 = base64.b64encode(buffered.getvalue()).decode()
                            
                            # Tumia Gemini kuangalia relevance
                            analysis_response = working_client.models.generate_content(
                                model="gemini-2.5-flash",
                                contents=[
                                    f"Prompt: {prompt}\n\n"
                                    f"Is this image related? Answer only 'YES' or 'NO'.",
                                    types.Part.from_bytes(
                                        data=base64.b64decode(img_base64),
                                        mime_type="image/png"
                                    )
                                ],
                                config=types.GenerateContentConfig(max_output_tokens=10)
                            )
                            
                            if "YES" in analysis_response.text.upper:
                                specific_images.append({
                                    "image": pil_image,
                                    "page": page_meta["page_number"],
                                    "filename": page_meta["pdf_name"],
                                    "description": f"Picha {img_index+1} kutoka ukurasa {page_meta['page_number']}",
                                    "relevance_score": analysis_response.text
                                })
                            
                            break  # Ikiwa imefanikiwa
                            
                        except Exception as e:
                            print(f"API error for image check: {e}")
                            continue
                else:
                    # Onyesha picha zote kama prompt haihusiani na picha
                    specific_images.append({
                        "image": pil_image,
                        "page": page_meta["page_number"],
                        "filename": page_meta["pdf_name"],
                        "description": f"Picha {img_index+1} kutoka ukurasa {page_meta['page_number']}",
                        "relevance_score": "Auto-included"
                    })
            
            doc.close()
            
        except Exception as e:
            print(f"Kosa katika kutoa picha kutoka ukurasa {page_meta['page_number']}: {e}")
    
    return specific_images

# Streamlit UI
st.markdown("<h5>📄 Mfumo wa kupata taarifa za Wanachama wa Azania 2006</h5>", unsafe_allow_html=True)
st.markdown("###### Andika Hitajio Lako") 
prompt = st.text_area("Andika hitajio lako", height=10, label_visibility="collapsed")

col1, col2 = st.columns([3, 1])
with col1:
    get_info = st.button("Pata taarifa")
with col2:
    get_images = st.button("Pata picha pia")

if get_info or get_images:
    if not prompt:
        st.warning("Andika swali kabla ya kubonyeza.")
    else:
        with st.spinner("Mchakato..."):
            try:
                # Pata majibu na kurasa zilizopendekezwa
                response_text, page_images, selected_pages = process_pdf_with_suggested_pages(prompt)
                
                # Onyesha majibu
                st.markdown("### 📋 Majibu:")
                st.info(response_text)
                
                # Kama user amebonyeza "Pata picha pia"
                if get_images and selected_pages:
                    st.markdown("### 📸 Picha za Kurasa Zilizochaguliwa:")
                    
                    # Onyesha picha za kurasa zote zilizochaguliwa
                    if page_images:
                        st.success(f"Nimepata picha za kurasa {len(page_images)} zilizochaguliwa")
                        
                        # Onyesha preview ya kila ukurasa
                        cols = st.columns(min(3, len(page_images)))
                        for idx, img_data in enumerate(page_images):
                            with cols[idx % 3]:
                                st.image(
                                    img_data["image"],
                                    caption=f"Ukurasa {img_data['page']} wa {img_data['filename']}",
                                    use_container_width=True
                                )
                    
                    # Extract picha maalum kutoka kwenye kurasa
                    st.markdown("### 🔍 Picha Maalum Zinazohusiana:")
                    specific_images = extract_specific_images(prompt, selected_pages)
                    
                    if specific_images:
                        st.success(f"Nimepata picha {len(specific_images)} maalum:")
                        
                        # Onyesha picha maalum
                        image_cols = st.columns(min(3, len(specific_images)))
                        for idx, img_data in enumerate(specific_images):
                            with image_cols[idx % 3]:
                                st.image(
                                    img_data["image"],
                                    caption=img_data["description"],
                                    use_container_width=True
                                )
                    else:
                        st.info("Hakuna picha maalum zilizopatikana kwenye kurasa hizi.")
                
            except Exception as e:
                st.error(f"Kosa limetokea: {e}")
                st.error("Tafadhali hakikisha unaweka API keys sahihi na PDF ziko kwenye folder 'data/'")