import streamlit as st
import pandas as pd

from social_templates import add_template, load_templates, delete_template

st.title("\U0001F4E3 Social Media Templates")

with st.sidebar:
    with st.form("template_form", clear_on_submit=True):
        title = st.text_input("Title")
        platform = st.text_input("Platform")
        content = st.text_area("Template")
        submitted = st.form_submit_button("Save template")

if submitted and title and platform and content:
    add_template(title, platform, content)
    st.experimental_rerun()

templates = load_templates()
if templates:
    df = pd.DataFrame(templates)
    df["delete"] = False
    edited = st.data_editor(
        df,
        column_config={
            "delete": st.column_config.CheckboxColumn("Delete", default=False),
            "id": None,
        },
        hide_index=True,
    )
    to_delete = edited.loc[edited["delete"], "id"].tolist()
    if to_delete:
        for template_id in to_delete:
            delete_template(template_id)
        st.experimental_rerun()
else:
    st.info("No templates yet.")
