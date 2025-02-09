import streamlit as st
import pandas as pd
import tempfile
import os
from azure.ai.formrecognizer import DocumentAnalysisClient
from azure.core.credentials import AzureKeyCredential
from io import BytesIO

# Azure Form Recognizer credentials
endpoint = ""
key = ""

def validate_page_range(page_range_str):
    """Validate and parse page range string"""
    try:
        if not page_range_str.strip():  # If empty, process all pages
            return None
        
        ranges = []
        parts = page_range_str.replace(' ', '').split(',')
        
        for part in parts:
            if '-' in part:
                start, end = map(int, part.split('-'))
                if start > end:
                    raise ValueError
                ranges.append((start, end))
            else:
                page = int(part)
                ranges.append((page, page))
        
        return ranges
    except:
        raise ValueError("Invalid page range format")

def process_pdf(file, page_ranges=None):
    try:
        document_analysis_client = DocumentAnalysisClient(
            endpoint=endpoint, credential=AzureKeyCredential(key)
        )

        try:
            poller = document_analysis_client.begin_analyze_document(
                "prebuilt-document", document=file)
            result = poller.result()
        except Exception as e:
            st.error(f"Error analyzing document: {str(e)}")
            return []

        all_tables = []
        table_num = 1

        for table in result.tables:
            page_num = table.bounding_regions[0].page_number if table.bounding_regions else None
            
            # Skip if page is not in specified ranges
            if page_ranges and page_num:
                in_range = False
                for start, end in page_ranges:
                    if start <= page_num <= end:
                        in_range = True
                        break
                if not in_range:
                    continue

            table_data = []
            for row in range(table.row_count):
                table_row = []
                for col in range(table.column_count):
                    cell = next((cell for cell in table.cells if cell.row_index ==
                                row and cell.column_index == col), None)
                    table_row.append(cell.content if cell else "")
                table_data.append(table_row)

            all_tables.append({
                "page": page_num,
                "table_num": table_num,
                "data": table_data
            })
            table_num += 1

        return all_tables
    except Exception as e:
        st.error(f"Error in process_pdf: {str(e)}")
        return []

def create_excel(tables):
    output = BytesIO()
    all_dfs = []
    for table in tables:
        df = pd.DataFrame(table["data"])
        df.insert(0, "Table", table["table_num"])
        df.insert(1, "Page", table["page"])
        all_dfs.append(df)

    final_df = pd.concat(all_dfs, ignore_index=True)
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        final_df.to_excel(writer, sheet_name='All Tables', index=False)

    output.seek(0)
    return output

def main():
    st.title("PDF Table Extractor")

    # Add a sidebar for configuration
    with st.sidebar:
        st.header("Configuration")
        # Add page range input
        page_range = st.text_input(
            "Page Range",
            placeholder="e.g., 1-3, 5, 7-9",
            help="Enter page ranges (e.g., '1-3, 5, 7-9'). Leave empty to process all pages."
        )

    uploaded_file = st.file_uploader("Choose a PDF file", type="pdf")

    if uploaded_file is not None:
        # Validate page range
        page_ranges = None
        try:
            if page_range:
                page_ranges = validate_page_range(page_range)
        except ValueError:
            st.error("Invalid page range format. Please use format like '1-3, 5, 7-9'")
            return

        st.write("File uploaded successfully!")

        if st.button("Process PDF"):
            with st.spinner("Processing PDF..."):
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
                    tmp_file.write(uploaded_file.getvalue())
                    tmp_file_path = tmp_file.name

                with open(tmp_file_path, "rb") as file:
                    tables = process_pdf(file, page_ranges)

                os.unlink(tmp_file_path)

                if tables:
                    st.success(f"Successfully extracted {len(tables)} tables from the PDF!")

                    # Create Excel file
                    excel_file = create_excel(tables)

                    # Download button for Excel
                    st.download_button(
                        label="📥 Download Excel",
                        data=excel_file,
                        file_name="extracted_tables.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )

                    # Display data
                    st.subheader("Extracted Tables")
                    all_dfs = []
                    for table in tables:
                        df = pd.DataFrame(table["data"])
                        df.insert(0, "Table", table["table_num"])
                        df.insert(1, "Page", table["page"])
                        all_dfs.append(df)

                    final_df = pd.concat(all_dfs, ignore_index=True)
                    st.dataframe(final_df)
                else:
                    st.warning("No tables found in the document.")

if __name__ == "__main__":
    main()
