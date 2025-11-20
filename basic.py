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

api_key=st.secrets["GOOGLE_API_KEY"]
api_key1=st.secrets["GOOGLE_API_KEY1"]
api_key2=st.secrets["GOOGLE_API_KEY2"]
client = genai.Client(api_key=api_key) 

for key in [api_key,api_key1,api_key2]:
    try:
        key=key
        client = genai.Client(api_key=key)
    except errors.APIError as e:
        continue
    
# prompt=input("Inter input: ")
# image=Image.open("../rag_demo/image01.png")
# chat=client.chats.create(model="gemini-2.5-pro")
# userinput=input("User :")
# while userinput != "endchat": 
#     chat.append(f"User :{userinput}") 
#     response=client.models.generate_content(
#         model="gemini-2.5-pro",
#         contents=chat,
#         config=types.GenerateContentConfig(
#             system_instruction="Answer 1 line not more than 50 words"
#         ))
#     chat.append(f"chatbot : {response.text}")
#     print(response.text)
#     userinput=input("User :")

# while userinput!="endchat":
#     response=chat.send_message(userinput)
#     print("statbot :",response.text)
#     userinput=input("User :")

# grounding_tools=types.Tool(
#     google_search=types.GoogleSearch()
# )

# response=client.models.generate_content(
#     model="gemini-2.5-flash",
#     contents="Who won uero cup 2024",
#     config=types.GenerateContentConfig(
#         tools=[grounding_tools]
#     )
# )
# print(response.text)

filepath=Path("AZANIA.pdf")
doc_dat=filepath.read_bytes()

pdf=types.Part.from_bytes(
    data=doc_dat,
    mime_type="application/pdf"
)

response=client.models.generate_content(
    model="gemini-2.5-flash",
    contents=f"Naomba unipatie taarifa yoyote itakayo uliziwa katika hii {pdf} ,hii ni data zetu za kawaida ya kikundi chetu {pdf} naomba utoe jibu kwa lugha ya kiswahili iliyorasmi na huu ujembe 'Based on the OCR text' usiuonyeshe"
)

print(response.text)

load_dotenv()

try:
   client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY")) 
except Exception as e:
    st.error("Tatizo la kuunganisha na Gemini API. Hakikisha umeweka GEMINI_API_KEY kwenye faili la .env.")
    st.stop()

def process_pdf_and_query(user_prompt):

    pdf=types.Part.from_bytes(
        data=doc_dat,
        mime_type="application/pdf"
    )
    contents = [pdf, user_prompt]

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=contents
    )

    return response.text

st.markdown("<h5>📄 Mfumo wa kupata taarifa za Wanachama wa Azania 2006</h5>", unsafe_allow_html=True)

# uploaded_file = st.file_uploader(
#     "Pakia faili lako la PDF (Maks. 20MB)", 
#     type=["pdf"]
# )

# if uploaded_file is not None:
#     # Onyesha faili limepakuliwa
#     st.success(f"Faili **{uploaded_file.name}** limepakuliwa kwa mafanikio.")
    
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