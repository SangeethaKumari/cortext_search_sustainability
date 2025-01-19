import streamlit as st  # Import Streamlit
from snowflake.snowpark import Session  # Import Snowflake Snowpark
import pandas as pd
import json

# Display App Title and Description
st.title(":green_heart: Chat Document Assistant on Sustainability")
st.markdown("""
This app helps you explore and answer sustainability-related questions based on uploaded documents.
Ask questions about topics like recycling, circular economy, infrastructure resilience, and more!
""")

# Add a section to list sample questions
st.subheader("Sample Questions You Can Ask:")
with st.expander("Click here to see example questions"):
    st.markdown("""
    **WWF Report 2024:**
    - What steps is WWF taking to address food waste and its environmental impact?
    - How has the Wildlife Adaptation Innovation Fund supported wildlife conservation?
    - What progress has WWF made in managing global grasslands?

    **EPA Circular Economy Progress Report 2022:**
    - What actions are outlined in the National Recycling Strategy to modernize the U.S. recycling system?
    - How does the Save Our Seas 2.0 Act aim to address plastic waste issues?
    - What initiatives has the EPA introduced to promote a circular economy for all?

    **EPA Sustainability Report and Implementation Plan 2020:**
    - What energy efficiency improvements have EPA facilities achieved since FY 2003?
    - How has the EPA reduced its water intensity over recent years?
    - What strategies has the EPA implemented to manage non-hazardous waste effectively?

    **Sustainable and Resilient Infrastructure Report:**
    - How does sustainable infrastructure align with the UN's Sustainable Development Goals?
    - What are the key principles for sustainable infrastructure development mentioned in the UNEP report?
    - How does natural infrastructure contribute to ecosystem restoration and resilience?
    """)

# Placeholder for user input
st.subheader("Ask Your Sustainability Question Below:")
question = st.text_input("Enter your question:", placeholder="e.g., What is the EPA's strategy for managing food waste?")

# Add a line to clarify that the app focuses on sustainability-related questions
st.sidebar.title(":seedling: About This App")
st.sidebar.markdown("""
This app specializes in answering sustainability-related questions based on uploaded documents.
It covers topics like climate change, recycling, sustainable development, and environmental conservation.
""")

# Configure pandas to display all content in cells
pd.set_option("max_colwidth", None)

# Load Snowflake connection parameters from config.json

with open("config/config.json", "r") as f:
    config = json.load(f)
# Constants
NUM_CHUNKS = 3  # Number of chunks for context
CORTEX_SEARCH_TABLE = "docs_chunks_table"  # Name of the table
CONNECTION_PARAMS = {
    "account": config["SNOWFLAKE_ACCOUNT"],
    "user": config["SNOWFLAKE_USER"],
    "password": config["SNOWFLAKE_PASSWORD"],
    "role": config["SNOWFLAKE_ROLE"],
    "warehouse": config["SNOWFLAKE_WAREHOUSE"],
    "database": config["SNOWFLAKE_DATABASE"],
    "schema": config["SNOWFLAKE_SCHEMA"],
}

# Establish Snowflake session
session = Session.builder.configs(CONNECTION_PARAMS).create()


### Functions

def list_documents():
    """Fetch the list of unique documents."""
    docs = session.sql(f"SELECT DISTINCT relative_path FROM {CORTEX_SEARCH_TABLE}").collect()
    return [doc.RELATIVE_PATH for doc in docs]


def config_options():
    """Configure sidebar options."""
    # Model selection
    st.sidebar.selectbox(
        "Select your model:",
        (
            "mixtral-8x7b",
            "snowflake-arctic",
            "mistral-large",
            "llama3-8b",
            "llama3-70b",
            "reka-flash",
            "mistral-7b",
            "llama2-70b-chat",
            "gemma-7b",
        ),
        key="model_name",
    )

    # Fetch categories
    categories = session.sql(f"SELECT DISTINCT category FROM {CORTEX_SEARCH_TABLE}").collect()
    cat_list = ["ALL"] + [cat.CATEGORY for cat in categories]

    # Category selection
    st.sidebar.selectbox("Select what category you are looking for", cat_list, key="category_value")

    # Display session state for debugging
    st.sidebar.expander("Session State").write(st.session_state)


def get_similar_chunks_search_service(query):
    """Fetch similar chunks based on the query."""
    category = st.session_state.get("category_value", "ALL")
    num_chunks = NUM_CHUNKS

    # Formulate the query
    if category == "ALL":
        sql_query = f"""
            SELECT chunk, relative_path, category
            FROM {CORTEX_SEARCH_TABLE}
            WHERE chunk ILIKE '%{query}%'
            LIMIT {num_chunks}
        """
    else:
        sql_query = f"""
            SELECT chunk, relative_path, category
            FROM {CORTEX_SEARCH_TABLE}
            WHERE chunk ILIKE '%{query}%'
              AND category = '{category}'
            LIMIT {num_chunks}
        """

    # Execute the query
    results = session.sql(sql_query).collect()
    response = {
        "results": [{"chunk": row.CHUNK, "relative_path": row.RELATIVE_PATH, "category": row.CATEGORY} for row in results]
    }

    # Display response in sidebar
    st.sidebar.json(response)
    return response


def create_prompt(myquestion):
    """Create a prompt based on the question."""
    if st.session_state.rag == 1:
        prompt_context = get_similar_chunks_search_service(myquestion)

        prompt = f"""
           You are an expert assistant that extracts information from the CONTEXT provided
           between <context> and </context> tags.
           When answering the question contained between <question> and </question> tags,
           be concise and do not hallucinate. 
           If you don’t have the information, just say so.
           Only answer the question if you can extract it from the CONTEXT provided.
           
           <context>          
           {prompt_context}
           </context>
           <question>  
           {myquestion}
           </question>
           Answer: 
           """

        relative_paths = {item["relative_path"] for item in prompt_context["results"]}
    else:
        prompt = f"Question: {myquestion} Answer: "
        relative_paths = "None"

    return prompt, relative_paths


def complete(myquestion):
    """Send the prompt to the AI model."""
    prompt, relative_paths = create_prompt(myquestion)

    cmd = """
        SELECT snowflake.cortex.complete(?, ?) AS response
    """
    df_response = session.sql(cmd, params=[st.session_state.model_name, prompt]).collect()
    return df_response, relative_paths


### Main Function

def main():
    st.title(":speech_balloon: Chat Document Assistant with Snowflake Cortex")
    st.write("This is the list of documents you already have and that will be used to answer your questions:")

    # List available documents
    docs_available = list_documents()
    if not docs_available:
        st.write("No documents found in the database.")
    else:
        st.dataframe(docs_available)

    # Sidebar configurations
    config_options()

    # Checkbox for using custom documents
    st.session_state.rag = st.sidebar.checkbox("Use your own documents as context?")

    # Input for user question
    question = st.text_input("Enter question", placeholder="What is the major cause of pollution?", label_visibility="collapsed")

    # If question is entered, process it
    if question:
        response, relative_paths = complete(question)
        res_text = response[0].RESPONSE
        st.markdown(res_text)

        # Show related documents in the sidebar
        if relative_paths != "None":
            with st.sidebar.expander("Related Documents"):
                for path in relative_paths:
                    st.sidebar.markdown(f"Document: {path}")


# Run the app
if __name__ == "__main__":
    main()
