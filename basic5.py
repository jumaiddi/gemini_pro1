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
import sys
import importlib.util

# Load environment variables
load_dotenv()

# Initialize working client
working_client = None
api_key = st.secrets.get("GOOGLE_API_KEY", "")
api_key1 = st.secrets.get("GOOGLE_API_KEY1", "")
api_key2 = st.secrets.get("GOOGLE_API_KEY2", "")

# Test API keys
for key in [api_key, api_key1, api_key2]:
    if key:
        try:
            client = genai.Client(api_key=key)
            client.models.list()
            working_client = client
            break
        except errors.APIError as e:
            continue
        except Exception as e:
            continue

# Load basic1.py as module
def load_basic1_module():
    """Load basic1.py as a module"""
    try:
        # Import the basic1.py file directly
        import basic1
        
        # Check if the required functions exist
        if hasattr(basic1, 'process_pdf_and_query'):
            return basic1
        else:
            st.error("basic1.py haina function 'process_pdf_and_query'")
            return None
    except ImportError as e:
        # Try to load from current directory
        try:
            # Create module from file
            spec = importlib.util.spec_from_file_location("basic1", "basic1.py")
            basic1_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(basic1_module)
            return basic1_module
        except Exception as e:
            st.error(f"Haiwezi kuload basic1.py: {str(e)}")
            return None

# Load the module
basic1_module = load_basic1_module()

if not working_client:
    st.sidebar.warning("⚠️ Hakuna API key inayofanya kazi. Programu itatumia text search pekee.")

# Read PDF files
data_folder = Path("./data")
pdf_pages_data = []  # Store page data

# Read PDF and split into pages
for pdf_filepath in data_folder.glob("*.pdf"):
    try:
        # Open PDF and split into pages
        doc = fitz.open(pdf_filepath)
        pdf_name = pdf_filepath.name
        
        for page_num in range(len(doc)):
            # Get PDF page as image
            page = doc[page_num]
            pix = page.get_pixmap()
            img_bytes = pix.tobytes("png")
            
            # Convert to PIL Image
            pil_image = Image.open(io.BytesIO(img_bytes))
            
            # Create single page PDF
            temp_pdf = fitz.open()
            temp_pdf.insert_pdf(doc, from_page=page_num, to_page=page_num)
            temp_pdf_bytes = temp_pdf.write()
            temp_pdf.close()
            
            # Store page data
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
                "page_text": page.get_text("text")
            })
        
        doc.close()
        
    except Exception as e:
        st.error(f"❌ {pdf_filepath.name}: {str(e)}")

# Cache for faster performance
@st.cache_data(ttl=3600, show_spinner=False)
def get_relevant_pages_smart(user_prompt):
    """Use only text-based search, NO API calls"""
    relevant_pages = []
    
    if not pdf_pages_data:
        return []
    
    # Extract keywords from prompt
    prompt_keywords = []
    for word in user_prompt.lower().split():
        if len(word) > 3:
            prompt_keywords.append(word)
    
    if not prompt_keywords:
        prompt_keywords = [user_prompt.lower()]
    
    # Search through all pages
    for page_data in pdf_pages_data:
        text = page_data["page_text"].lower()
        
        # Check each keyword
        match_count = 0
        matched_words = []
        for keyword in prompt_keywords:
            if keyword in text:
                match_count += 1
                matched_words.append(keyword)
        
        if match_count > 0:
            # Find context
            context = ""
            lines = page_data["page_text"].split('\n')
            for i, line in enumerate(lines):
                line_lower = line.lower()
                if any(keyword in line_lower for keyword in matched_words):
                    start = max(0, i-2)
                    end = min(len(lines), i+3)
                    context_lines = lines[start:end]
                    context = ' '.join(context_lines)
                    break
            
            relevant_pages.append({
                "pdf_name": page_data["pdf_name"],
                "page_number": page_data["page_number"],
                "data": page_data["pdf_data"],
                "image": page_data["image"],
                "page_text": page_data["page_text"],
                "match_score": match_count,
                "matched_words": matched_words,
                "description": f"Maneno {len(matched_words)} yalipatikana",
                "context": context[:300] + "..." if len(context) > 300 else context
            })
    
    # Sort by match score
    relevant_pages.sort(key=lambda x: x["match_score"], reverse=True)
    
    return relevant_pages[:5]

def safe_api_call(contents, max_retries=2):
    """Make API call with retry logic"""
    for key in [api_key, api_key1, api_key2]:
        for attempt in range(max_retries):
            try:
                client = genai.Client(api_key=key)
                response = client.models.generate_content(
                    model="gemini-1.5-flash",
                    contents=contents,
                    config=types.GenerateContentConfig(
                        max_output_tokens=500,
                        temperature=0.3
                    )
                )
                return response.text, True
            except errors.APIError as e:
                if "429" in str(e) and attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    time.sleep(wait_time)
                    continue
                else:
                    break
            except Exception as e:
                break
    return None, False

def process_with_basic1(prompt):
    """Use basic1.py module for text explanation"""
    if basic1_module:
        try:
            # Prepare PDF data for basic1
            all_pdf_data = []
            for page in pdf_pages_data:
                all_pdf_data.append(page["pdf_data"])
            
            # Call basic1 function
            response = basic1_module.process_pdf_and_query(prompt)
            return response
        except Exception as e:
            st.error(f"Kosa katika basic1: {str(e)}")
            return None
    return None

def process_pdf_with_suggested_pages(user_prompt, use_basic1=False):
    """Get information from relevant pages"""
    # Get relevant pages
    relevant_pages = get_relevant_pages_smart(user_prompt)
    
    if not relevant_pages:
        return "Samahani, sijaona kurasa zinazohusiana na swali lako.", [], []
    
    # If using basic1 for text explanation
    if use_basic1:
        basic1_response = process_with_basic1(user_prompt)
        if basic1_response:
            return basic1_response, relevant_pages, []
    
    # Ask user to select pages
    selected_pages = []
    if len(relevant_pages) > 1:
        st.write("### 📄 Chagua Kurasa:")
        
        cols = st.columns(min(3, len(relevant_pages)))
        selected_indices = []
        
        for i, page in enumerate(relevant_pages):
            with cols[i % 3]:
                st.image(
                    page["image"],
                    caption=f"Ukurasa {page['page_number']}",
                    use_container_width=True
                )
                
                st.caption(f"**Matched:** {', '.join(page['matched_words'][:2])}")
                
                if st.checkbox(
                    f"Chagua ukurasa {page['page_number']}",
                    key=f"select_page_{i}",
                    value=True
                ):
                    selected_indices.append(i)
        
        selected_pages = [relevant_pages[i] for i in selected_indices]
    else:
        selected_pages = relevant_pages
        st.image(
            relevant_pages[0]["image"],
            caption=f"Ukurasa {relevant_pages[0]['page_number']}",
            use_container_width=True
        )
    
    if not selected_pages:
        return "Hujachagua kurasa yoyote. Tafadhali chagua angalau ukurasa mmoja.", [], []
    
    # Try to get answer from API if available
    response_text = ""
    api_used = False
    
    if working_client and len(selected_pages) <= 2:
        try:
            contents = [
                f"Swali la mtumiaji: {user_prompt}\n\n"
                f"Jibu kulingana na kurasa {len(selected_pages)} zilizochaguliwa.\n\n"
                f"Ukurasa 1: {selected_pages[0].get('context', '')[:500]}"
            ]
            
            if len(selected_pages) == 1:
                contents.append(selected_pages[0]["data"])
            
            api_response, api_success = safe_api_call(contents)
            
            if api_success:
                response_text = f"**🤖 Majibu (Gemini API):**\n\n{api_response}"
                api_used = True
            else:
                response_text = "**ℹ️ Taarifa (Bila API):**\n\n"
        
        except Exception as e:
            response_text = "**ℹ️ Taarifa (Bila API):**\n\n"
    
    else:
        response_text = "**ℹ️ Taarifa (Bila API):**\n\n"
    
    # Build text-based response
    if not api_used:
        response_text += f"Nimepata **{len(selected_pages)} kurasa** zinazohusiana:\n\n"
        
        for page in selected_pages:
            response_text += f"**📄 Ukurasa {page['page_number']} wa {page['pdf_name']}:**\n"
            response_text += f"**Maneno yaliyopatika:** {', '.join(page['matched_words'][:5])}\n"
            
            if page.get('context'):
                response_text += f"**Muktadha:** {page['context']}\n"
            
            response_text += "\n"
        
        response_text += "\n---\n"
        response_text += "**💡 Usaidizi:**\n"
        response_text += "1. Tumia maneno mahususi zaidi kwa matokeo bora\n"
        response_text += "2. Jaribu kutumia 'Text Explanation' option\n"
    
    return response_text, selected_pages, []

def extract_images_from_pages(selected_pages):
    """Extract images from selected pages"""
    extracted_images = []
    
    for page_meta in selected_pages:
        try:
            doc = fitz.open(stream=page_meta["data"].file_data, filetype="pdf")
            page = doc[0]
            
            images = page.get_images()
            for img_index, img in enumerate(images[:3]):
                xref = img[0]
                base_image = doc.extract_image(xref)
                image_bytes = base_image["image"]
                
                pil_image = Image.open(io.BytesIO(image_bytes))
                
                if pil_image.width > 50 and pil_image.height > 50:
                    extracted_images.append({
                        "image": pil_image,
                        "page": page_meta["page_number"],
                        "pdf_name": page_meta["pdf_name"],
                        "image_index": img_index + 1,
                        "description": f"Picha {img_index+1} - Ukurasa {page_meta['page_number']}"
                    })
            
            doc.close()
            
        except Exception as e:
            st.warning(f"Shida kuchukua picha kutoka ukurasa {page_meta['page_number']}")
    
    return extracted_images

# Streamlit UI
st.set_page_config(
    page_title="Mfumo wa Taarifa - Azania 2006",
    page_icon="📄",
    layout="wide"
)

# Sidebar with mode selection
with st.sidebar:
    st.title("⚙️ Chagua Njia ya Utafutaji")
    st.markdown("---")
    
    # Mode selection
    search_mode = st.radio(
        "**Chagua aina ya utafutaji:**",
        ["normal", "text_explanation", "image_search"],
        format_func=lambda x: {
            "normal": "🔍 Utafutaji wa Kawaida",
            "text_explanation": "📝 Text Explanation (basic1)",
            "image_search": "📸 Utafutaji wa Picha"
        }[x]
    )
    
    st.markdown("---")
    
    # System info
    # st.write("### 📊 Maelezo ya Mfumo")
    # st.write(f"📄 Kurasa Zote: {len(pdf_pages_data)}")
    
    # api_status = "✅ Inatumika" if working_client else "❌ Haipatikani"
    # st.write(f"🤖 API Status: {api_status}")
    
    # basic1_status = "✅ Imeload" if basic1_module else "❌ Haijaload"
    # st.write(f"📝 basic1 Module: {basic1_status}")
    
    if not basic1_module:
        st.error("Haiwezi kuload basic1.py. Hakikisha iko katika folder ile ile.")

# Main content
st.title("📄 Mfumo wa Taarifa - Azania 2006")
st.markdown("---")

# Show current mode
mode_display = {
    "normal": "🔍 Utafutaji wa Kawaida",
    "text_explanation": "📝 Text Explanation (basic1 Module)",
    "image_search": "📸 Utafutaji wa Picha"
}
st.info(f"**Hali ya Sasa:** {mode_display[search_mode]}")

# Search input
col1, col2 = st.columns([4, 1])
with col1:
    prompt = st.text_input(
        "🔍 **Andika hitajio lako:**",
        placeholder="Mfano: jina la mwanachama, namba ya kumbukumbu..."
    )

with col2:
    st.write("")  # Spacing
    st.write("")  # Spacing
    get_images = st.checkbox("📸 Pata picha", value=(search_mode == "image_search"))

# Buttons
col_btn1, col_btn2, col_btn3 = st.columns(3)
with col_btn1:
    search_btn = st.button("🔍 Tafuta Taarifa", type="primary", use_container_width=True)
with col_btn2:
    clear_btn = st.button("🗑️ Futa Yote", use_container_width=True)
with col_btn3:
    preview_btn = st.button("👁️ Angalia Kurasa Zote", use_container_width=True)

# Handle clear button
if clear_btn:
    st.rerun()

# Handle preview button
if preview_btn:
    st.markdown("### 📚 Kurasa Zote Zilizosomwa")
    
    if not pdf_pages_data:
        st.warning("Hakuna PDF files zilizosomwa.")
    else:
        pdf_groups = {}
        for page in pdf_pages_data:
            pdf_name = page["pdf_name"]
            if pdf_name not in pdf_groups:
                pdf_groups[pdf_name] = []
            pdf_groups[pdf_name].append(page)
        
        for pdf_name, pages in pdf_groups.items():
            with st.expander(f"📖 {pdf_name} ({len(pages)} kurasa)", expanded=False):
                cols = st.columns(min(4, len(pages)))
                for idx, page in enumerate(pages):
                    with cols[idx % 4]:
                        st.image(
                            page["image"],
                            use_container_width=True
                        )
                        st.caption(f"Ukurasa {page['page_number']}")

# Handle search button
if search_btn and prompt:
    with st.spinner("🔍 Inatafuta taarifa..."):
        try:
            # MODE 1: TEXT EXPLANATION (basic1 module)
            if search_mode == "text_explanation":
                st.markdown("## 📝 Text Explanation (basic1 Module)")
                st.markdown("---")
                
                if basic1_module:
                    response_text = process_with_basic1(prompt)
                    if response_text:
                        st.info(response_text)
                        st.success("✅ Maelezo yametolewa kwa kutumia basic1.py module")
                    else:
                        st.warning("Haiwezi kupata maelezo kutoka basic1. Jaribu njia nyingine.")
                else:
                    st.error("basic1 module haijaload. Hakikisha basic1.py iko katika folder ile ile.")
            
            # MODE 2: IMAGE SEARCH
            elif search_mode == "image_search" or get_images:
                response_text, selected_pages, page_info = process_pdf_with_suggested_pages(prompt)
                
                # Display results
                st.markdown("## 📸 Matokeo ya Utafutaji wa Picha")
                st.markdown("---")
                
                if selected_pages:
                    st.markdown(f"### 📄 Kurasa Zilizochaguliwa ({len(selected_pages)})")
                    
                    # Display each selected page
                    page_cols = st.columns(min(3, len(selected_pages)))
                    for idx, page in enumerate(selected_pages):
                        with page_cols[idx % 3]:
                            st.image(
                                page["image"],
                                caption=f"**{page['pdf_name']}** - Ukurasa {page['page_number']}",
                                use_container_width=True
                            )
                    
                    # Extract and show images
                    if get_images:
                        st.markdown("### 📸 Picha Zilizobainika")
                        extracted_images = extract_images_from_pages(selected_pages)
                        
                        if extracted_images:
                            st.success(f"✅ Nimepata picha {len(extracted_images)}")
                            
                            img_cols = st.columns(min(4, len(extracted_images)))
                            for idx, img_data in enumerate(extracted_images):
                                with img_cols[idx % 4]:
                                    st.image(
                                        img_data["image"],
                                        caption=img_data["description"],
                                        use_container_width=True
                                    )
                        else:
                            st.info("ℹ️ Hakuna picha zilizopatikana kwenye kurasa hizi.")
            
            # MODE 3: NORMAL SEARCH
            else:
                response_text, selected_pages, page_info = process_pdf_with_suggested_pages(prompt, use_basic1=False)
                
                st.markdown("## 📋 Matokeo ya Utafutaji")
                st.markdown("---")
                
                # Display response text
                st.markdown(response_text)
                
                # Show selected pages
                if selected_pages:
                    st.markdown(f"### 📄 Kurasa Zilizochaguliwa ({len(selected_pages)})")
                    
                    page_cols = st.columns(min(3, len(selected_pages)))
                    for idx, page in enumerate(selected_pages):
                        with page_cols[idx % 3]:
                            st.image(
                                page["image"],
                                caption=f"**{page['pdf_name']}** - Ukurasa {page['page_number']}",
                                use_container_width=True
                            )
            
            # Quota warning
            if not working_client and search_mode != "text_explanation":
                st.warning("""
                ⚠️ **API Haipatikani kwa Sasa:**
                - Quota ya Gemini API imekwisha
                - Jaribu kutumia 'Text Explanation' option
                """)
            
        except Exception as e:
            st.error(f"❌ Kosa limetokea: {str(e)}")

elif search_btn and not prompt:
    st.warning("⚠️ Tafadhali andika hitajio lako kabla ya kubonyeza 'Tafuta Taarifa'.")

# Footer
st.markdown("---")
st.markdown(f"""
<div style='text-align: center'>
    <small>📊 Mfumo wa Taarifa - Azania 2006 | 
    <span style='color: green'>Mode: {mode_display[search_mode]}</span> | 
    Modules: basic4 + {'basic1' if basic1_module else 'none'}</small>
</div>
""", unsafe_allow_html=True)

# Initialize session state for chat history
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []