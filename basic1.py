from google import genai
import os
from dotenv import load_dotenv
from google.genai import types
from google.genai import errors
from PIL import Image
from pathlib import Path
import streamlit as st
import base64

load_dotenv()
working_client=None
api_key=st.secrets["GOOGLE_API_KEY"]
api_key1=st.secrets["GOOGLE_API_KEY1"]
api_key2=st.secrets["GOOGLE_API_KEY2"]
for key in [api_key,api_key1,api_key2]:
    try:
        key=key
        client = genai.Client(api_key=key)
        client.models.list()
        working_client=client
        break
    except errors.APIError as e:
        continue

data_folder = Path("./data1")
all_pdf_data=[]

for pdf_filepath in data_folder.glob("*.pdf"):
    doc_dat = pdf_filepath.read_bytes()
    pdf=types.Part.from_bytes(
    data=doc_dat,
    mime_type="application/pdf"
    )
    all_pdf_data.append(pdf)
    print(f"Nimesoma faili kwa mafanikio: {pdf_filepath.name}")
    
def process_pdf_and_query(user_prompt):
    contents = [all_pdf_data, user_prompt]
    response_text=None
    for key in [api_key,api_key1,api_key2]:
        try:
            working_client = genai.Client(api_key=key)
            response = working_client.models.generate_content(
                model="gemini-2.5-flash",
                contents=contents,
            )
            print("HHHHHHHHHHHHHHHHHHHHHH ",response.text)
            response_text=response.text
            break
        except Exception as e:
            print("MMMMMMMMMMMMMMMMMM",e)
            continue
    return response_text
        


st.markdown("<h5>📄 Mfumo wa kupata taarifa za Wanachama wa Azania 2006</h5>", unsafe_allow_html=True)
    
st.markdown("###### Andika Hitajio Lako") 

prompt = st.text_area(
    "Andika hitajio lako",
    height=10,
    label_visibility="collapsed" 
)

if st.button("Pata taarifa"):
    if not prompt:
        st.warning("Andika swali kabla ya kubonyeza 'Pata Jibu'.")
    else:
        with st.spinner("Mchakato..."):
            try:
                # Ita kazi ya kuchakata na kupata jibu
                response_text = process_pdf_and_query(prompt)
                
                # st.subheader("Pata taarifa")
                st.info(response_text)
                
            except Exception as e:
                st.error(f"Kosa limetokea wakati wa kuwasiliana na API: {e}")