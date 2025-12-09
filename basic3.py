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
# all_pdf_data = []
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

def analyze_pdf_structure():
    """Analyz structure ya PDF na kugenereta metadata ya kurasa"""
    page_metadata = []
    for key in [api_key, api_key1, api_key2]:
        try:
            client = genai.Client(api_key=key)
            client.models.list()
            working_client = client
            
            print(f"✅ Key inatumika", key)
            
            # Flag ya kuona kama tumemaliza
            success = True
            
            for page_data in pdf_pages_data:
                try:
                    response = working_client.models.generate_content(
                        model="gemini-1.5-flash",
                        contents=[
                            "Analyze this PDF page...",
                            page_data["pdf_data"]
                        ]
                    )
                    
                    page_metadata.append({
                        "pdf_name": page_data["pdf_name"],
                        "page_number": page_data["page_number"],
                        "description": response.text,
                        "has_images": len(page_data["page_text"]),
                        "data": page_data["pdf_data"],
                        "image": page_data["image"]
                    })
                    
                except Exception as e:
                    print(f"XXXXXXXXXXXXXX Kosa: {e}")
                    success = False
                    break  # Toka kwenye inner loop
            
            # Ikiwa hakuna error
            if success:
                print("KKKKKKKKKKKKKKKK")
                return page_metadata  # Return na data
            else:
                print("ZZZZZZZZZZZZZZZZZZZZZZZZZZ")
                continue  # Jaribu key nyingine
                
        except Exception as e:
            print(f"Key failed: {e}")
            continue
    
    return page_metadata
def get_relevant_pages(user_prompt):
    """Pata kurasa zinazohusiana na prompt ya mtumiaji"""
    relevant_pages = []
    for key in [api_key, api_key1, api_key2]:
        try:
            client = genai.Client(api_key=key)
            client.models.list()
            working_client = client
            
            print(f"✅ Key inatumika", key)
            
            # Flag ya kuona kama tumemaliza
            success = True
            for page_meta in analyze_pdf_structure():
                try:
                    # Check if page is relevant to prompt
                    response = working_client.models.generate_content(
                        model="gemini-1.5-flash",
                        contents=[
                            f"Prompt: {user_prompt}\n\n"
                            f"Page description: {page_meta['description']}\n\n"
                            f"Answer with only 'YES' or 'NO' if this page is relevant to the prompt.",
                            page_meta["data"]
                        ]
                    )
                    
                    if "YES" in response.text.upper():
                        relevant_pages.append(page_meta)
                        
                except Exception as e:
                    print(f"Kosa: {e}")
                    success = False
                    break  # Toka kwenye inner loop
            
            # Ikiwa hakuna error
            if success:
                return relevant_pages  # Return na data
            else:
                continue  # Jaribu key nyingine
                
        except Exception as e:
            print(f"Key failed: {e}")
            continue
    
    return relevant_pages

def process_pdf_with_suggested_pages(user_prompt):
    """Pata majibu kutoka kwenye kurasa zilizopendekezwa"""
    # Pata kurasa zinazohusiana
    relevant_pages = get_relevant_pages(user_prompt)
    
    if not relevant_pages:
        return "Samahani, sijaona kurasa zinazohusiana na swali lako.", [], []
    
    # Ona kurasa zilizopatikana
    st.info(f"📄 Nimepata kurasa {len(relevant_pages)} zinazohusiana:")
    
    page_list = []
    for i, page in enumerate(relevant_pages):
        page_list.append(f"{i+1}. {page['pdf_name']} - Ukurasa {page['page_number']}: {page['description']}")
    
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
        try:
            # Pata majibu kutoka kwenye ukurasa maalum
            response = working_client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[
                    f"User prompt: {user_prompt}\n\n"
                    f"Answer based ONLY on this specific page {page_meta['page_number']} of {page_meta['pdf_name']}.",
                    page_meta["data"]
                ]
            )
            
            combined_response += f"\n\n**Ukurasa {page_meta['page_number']} wa {page_meta['pdf_name']}:**\n"
            combined_response += response.text
            
            # Hifadhi picha ya ukurasa
            all_page_images.append({
                "image": page_meta["image"],
                "page": page_meta["page_number"],
                "filename": page_meta["pdf_name"],
                "description": page_meta["description"]
            })
            
        except Exception as e:
            print(f"Kosa katika kusoma ukurasa {page_meta['page_number']}: {e}")
    
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
            for img_index, img in enumerate(images):
                xref = img[0]
                base_image = doc.extract_image(xref)
                image_bytes = base_image["image"]
                
                # Badilisha kuwa PIL Image
                pil_image = Image.open(io.BytesIO(image_bytes))
                
                # Angalia ikiwa picha inahusiana na prompt
                buffered = io.BytesIO()
                pil_image.save(buffered, format="PNG")
                img_base64 = base64.b64encode(buffered.getvalue()).decode()
                
                # Tumia Gemini kuangalia relevance
                analysis_response = working_client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=[
                        f"Prompt: {prompt}\n\n"
                        f"Is this image related to the prompt? Answer only 'YES' or 'NO'.",
                        types.Part.from_bytes(
                            data=base64.b64decode(img_base64),
                            mime_type="image/png"
                        )
                    ],
                    config=types.GenerateContentConfig(max_output_tokens=10)
                )
                
                if "YES" in analysis_response.text.upper():
                    specific_images.append({
                        "image": pil_image,
                        "page": page_meta["page_number"],
                        "filename": page_meta["pdf_name"],
                        "description": f"Picha {img_index+1} kutoka ukurasa {page_meta['page_number']}",
                        "relevance_score": analysis_response.text
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
                        st.success(f"Nimepata picha {len(specific_images)} maalum zinazohusiana:")
                        
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
                        st.warning("Hakuna picha maalum zilizohusiana moja kwa moja na swali lako.")
                
            except Exception as e:
                st.error(f"Kosa limetokea: {e}")
                st.error("Tafadhali hakikisha unaweka API keys sahihi na PDF ziko kwenye folder 'data/'")