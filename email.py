# === TAB 7: ANALYTICS & EXPORT ===
with tabs[7]:
    st.title("📊 Analytics & Export")
    df_main = read_students()

    # === Enrollment Chart ===
    st.subheader("📈 Student Enrollment Over Time")
    if not df_main.empty and "ContractStart" in df_main.columns:
        df_main["EnrollDate"] = pd.to_datetime(df_main["ContractStart"], errors='coerce')
        enroll_by_month = df_main.groupby(df_main["EnrollDate"].dt.to_period("M")).size().reset_index(name='Count')
        enroll_by_month["EnrollDate"] = enroll_by_month["EnrollDate"].astype(str)
        st.line_chart(enroll_by_month.set_index("EnrollDate")["Count"])
    else:
        st.info("No enrollment dates found for analysis.")

    # === Data Export ===
    st.subheader("⬇️ Export Data")
    if not df_main.empty:
        st.download_button("📁 Download All Students CSV", df_main.to_csv(index=False), file_name="all_students.csv")
    else:
        st.warning("No student data available to export.")
