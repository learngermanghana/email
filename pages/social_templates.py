import streamlit as st
import pandas as pd

from social_templates import add_template, load_templates, delete_template

st.title("\U0001F4E3 Social Media Templates")

with st.form("template_form", clear_on_submit=True):
    title = st.text_input("Title")
    platform = st.text_input("Platform")
    content = st.text_area("Template")
    submitted = st.form_submit_button("Save template")

if submitted and title and platform and content:
    add_template(title, platform, content)
    st.success("Template saved!")

templates = load_templates()
if templates:
    df = pd.DataFrame(templates).drop(columns=["id"]) if templates else pd.DataFrame()
    st.dataframe(df)
    for tmpl in templates:
        col1, col2, col3 = st.columns([3, 2, 1])
        with col1:
            st.write(f"**{tmpl['title']}** ({tmpl['platform']})")
        with col2:
            st.write(tmpl["content"])
        with col3:
            if st.button("Delete", key=f"del_{tmpl['id']}"):
                delete_template(tmpl["id"])
                st.experimental_rerun()
else:
    st.info("No templates yet.")
