import streamlit as st # Import python packages
from snowflake.snowpark.context import get_active_session

from snowflake.core import Root

import pandas as pd
import json


# Add custom CSS for the background image
st.markdown(
    """
    <style>
    body {
        background-color: #ADD8E6;
        background-size: cover;
        background-repeat: no-repeat;
        background-attachment: fixed;
    }

    /* Optional: Styling for the text to make it more readable */
    .stApp {
        background: rgba(255, 255, 255, 0.8);
        border-radius: 10px;
        padding: 15px;
        margin: auto;
        max-width: 1000px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    }
    </style>
    """,
    unsafe_allow_html=True
)


# Display App Title and Description
st.title(":airplane: Immigration Rules Assistant ")
st.markdown("""
This app helps you explore and answer immigration-related questions based on uploaded documents.
Ask questions about topics like different types of visa, how to obtain the visa, documents to fill and more!!
""")

# Add a section to list sample questions
st.subheader("Sample Questions You Can Ask:")
with st.expander("Click here to see example questions"):
    st.markdown("""
    **Visa Types**
    - L1
    - H1
    - F1

    **H1**
    - How to get L1 visa?
    """)

# Placeholder for user input
st.subheader("Ask Your Immigration Question Below:")
question = st.text_input("Enter your question:", placeholder="e.g.,How to get the H1 visa")

# Add a line to clarify that the app focuses on immigration-related questions
st.sidebar.title(":passport_control: About This App")
st.sidebar.markdown("""
This app specializes in answering immigration-related questions based on uploaded documents.
It covers different types of visa, how to obtain the visa, documents to fill and more.
""")
pd.set_option("max_colwidth",None)

### Default Values
NUM_CHUNKS = 3 # Num-chunks provided as context. Play with this to check how it affects your accuracy

# service parameters
CORTEX_SEARCH_DATABASE = "cortex_analyst_immigration_rules"
CORTEX_SEARCH_SCHEMA = "DATA"
CORTEX_SEARCH_SERVICE = "CC_SEARCH_SERVICE_CS"
######
######

# columns to query in the service
COLUMNS = [
    "chunk",
    "relative_path",
    "category"
]

session = get_active_session()
root = Root(session)                         

svc = root.databases[CORTEX_SEARCH_DATABASE].schemas[CORTEX_SEARCH_SCHEMA].cortex_search_services[CORTEX_SEARCH_SERVICE]
   
### Functions
     
def config_options():

    st.sidebar.selectbox('Select your model:',(
                                    'mixtral-8x7b',
                                    'snowflake-arctic',
                                    'mistral-large',
                                    'llama3-8b',
                                    'llama3-70b',
                                    'reka-flash',
                                     'mistral-7b',
                                     'llama2-70b-chat',
                                     'gemma-7b'), key="model_name")

    categories = session.sql("select category from CORTEX_ANALYST_IMMIGRATION_RULES.DATA.docs_chunks_table group by category").collect()

    cat_list = ['ALL']
    for cat in categories:
        cat_list.append(cat.CATEGORY)
            
    st.sidebar.selectbox('Select what category you are looking for', cat_list, key = "category_value")

    st.sidebar.expander("Session State").write(st.session_state)

def get_similar_chunks_search_service(query):

    if st.session_state.category_value == "ALL":
        response = svc.search(query, COLUMNS, limit=NUM_CHUNKS)
    else: 
        filter_obj = {"@eq": {"category": st.session_state.category_value} }
        response = svc.search(query, COLUMNS, filter=filter_obj, limit=NUM_CHUNKS)

    st.sidebar.json(response.json())
  

    
    return response.json()  

def create_prompt (myquestion):
    prompt_context = get_similar_chunks_search_service(myquestion)


    prompt = f"""
           You are an expert chat assistance that extracs information from the CONTEXT provided
           between <context> and </context> tags.
           When ansering the question contained between <question> and </question> tags
           be concise and do not hallucinate. 
           If you don´t have the information just say so.
           Only anwer the question if you can extract it from the CONTEXT provideed.
           
           Do not mention the CONTEXT used in your answer.
    
           <context>          
           {prompt_context}
           </context>
           <question>  
           {myquestion}
           </question>
           Answer: 
           """
    json_data = json.loads(prompt_context)

    relative_paths = set(item['relative_path'] for item in json_data['results'])
        
    
            
    return prompt, relative_paths

def complete(myquestion):

    prompt, relative_paths  =create_prompt (myquestion)
   # st.write(prompt)
   # print("Printing the entire prompt:", prompt.encode('ascii', errors='replace').decode('ascii'))
    cmd = """
            select snowflake.cortex.complete(?, ?) as response
          """
    
    df_response = session.sql(cmd, params=[st.session_state.model_name, prompt]).collect()
    return df_response, relative_paths 

def main():
    
    st.title(f":speech_balloon: Immigration Rules Assistant with Snowflake Cortex Search")
    st.write("This is the list of documents you already have and that will be used to answer your questions:")
   # docs_available = session.sql("ls @docs").collect()
    docs_available = session.sql("ls @CORTEX_ANALYST_IMMIGRATION_RULES.DATA.DOCS").collect()

    list_docs = []
    for doc in docs_available:
        list_docs.append(doc["name"])
    st.dataframe(list_docs)

    config_options()

    st.session_state.rag = st.sidebar.checkbox('Use your own documents as context?')

    question = st.text_input("Enter question", placeholder="What is the types of visa?", label_visibility="collapsed")

    if question:
        response, relative_paths = complete(question)
        res_text = response[0].RESPONSE
        st.markdown(res_text)
        #st.markdown(prompt_context)

        if relative_paths != "None":
            with st.sidebar.expander("Related Documents"):
                for path in relative_paths:
                    cmd2 = f"select GET_PRESIGNED_URL(@CORTEX_ANALYST_IMMIGRATION_RULES.DATA.DOCS, '{path}', 360) as URL_LINK from directory(@docs)"
                    df_url_link = session.sql(cmd2).to_pandas()
                    url_link = df_url_link._get_value(0,'URL_LINK')
        
                    display_url = f"Doc: [{path}]({url_link})"
                    st.sidebar.markdown(display_url)
                
if __name__ == "__main__":
    main()
