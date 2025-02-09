import streamlit as st
import pandas as pd
import tempfile
import os
from azure.ai.formrecognizer import DocumentAnalysisClient
from azure.core.credentials import AzureKeyCredential
from io import BytesIO
from schema.schema_generator import SchemaGenerator

# Azure Form Recognizer credentials
endpoint = ""
key = ""


def process_pdf(file):
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
            table_data = []
            for row in range(table.row_count):
                table_row = []
                for col in range(table.column_count):
                    cell = next((cell for cell in table.cells if cell.row_index ==
                                row and cell.column_index == col), None)
                    table_row.append(cell.content if cell else "")
                table_data.append(table_row)

            all_tables.append({
                "page": table.bounding_regions[0].page_number if table.bounding_regions else None,
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
        generate_schema = st.checkbox("Generate Schema YAML", value=True)
        
        if generate_schema:
            st.subheader("Schema Configuration")
            
            # Create a form for schema configuration
            with st.form(key='schema_config_form'):
                st.write("Enter Schema Configuration Values:")
                
                # Text input fields for schema configuration
                entity = st.text_input(
                    "Entity Name",
                    placeholder="Enter entity name (e.g., POSITION)"
                )
                
                record_marker = st.text_input(
                    "Record Marker",
                    placeholder="Enter record marker (e.g., RECORD)"
                )
                
                domain_header = st.text_input(
                    "Domain Header",
                    placeholder="Enter domain header (e.g., HEADER)"
                )
                
                domain_trailer = st.text_input(
                    "Domain Trailer",
                    placeholder="Enter domain trailer (e.g., TRAILER)"
                )
                
                # Submit button for the form
                submit_button = st.form_submit_button(label="Apply Configuration")
                
                if submit_button:
                    if not all([entity, record_marker, domain_header, domain_trailer]):
                        st.error("All fields are required. Please fill in all values.")
                    else:
                        st.session_state.schema_config = {
                            'entity': entity,
                            'record_marker': record_marker,
                            'domain_header': domain_header,
                            'domain_trailer': domain_trailer
                        }
                        st.success("Configuration saved successfully!")

    uploaded_file = st.file_uploader("Choose a PDF file", type="pdf")

    if uploaded_file is not None:
        st.write("File uploaded successfully!")

        if st.button("Process PDF"):
            # Validate schema configuration if generate_schema is enabled
            if generate_schema and not hasattr(st.session_state, 'schema_config'):
                st.error("Please configure schema settings in the sidebar before processing.")
                return

            with st.spinner("Processing PDF..."):
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
                    tmp_file.write(uploaded_file.getvalue())
                    tmp_file_path = tmp_file.name

                with open(tmp_file_path, "rb") as file:
                    tables = process_pdf(file)

                os.unlink(tmp_file_path)

                if tables:
                    st.success(f"Successfully extracted {len(tables)} tables from the PDF!")

                    # Create Excel file
                    excel_file = create_excel(tables)

                    # Create columns for download buttons
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.download_button(
                            label="📥 Download Excel",
                            data=excel_file,
                            file_name="extracted_tables.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        )

                    # Generate schema if enabled
                    if generate_schema and hasattr(st.session_state, 'schema_config'):
                        try:
                            with st.spinner("Generating schema..."):
                                if tables and len(tables) > 0:
                                    # Get the first table that contains schema information
                                    schema_table = None
                                    for table in tables:
                                        df = pd.DataFrame(table["data"])
                                        # Debug information
                                        st.write(f"Table {table['table_num']} on Page {table['page']}:")
                                        st.dataframe(df)  # Display each table for debugging
                                        
                                        if len(df.columns) >= 3 and not df.empty:
                                            # Check first row for required columns
                                            first_row = [str(cell).strip().upper() for cell in df.iloc[0]]
                                            st.write("First row:", first_row)  # Debug first row content
                                            
                                            # More flexible column matching
                                            has_field_name = any('FIELD' in str(cell).upper() and 'NAME' in str(cell).upper() for cell in first_row)
                                            has_pos = any('POS' in str(cell).upper() for cell in first_row)
                                            has_rec = any('REC' in str(cell).upper() and '#' in str(cell) for cell in first_row)
                                            
                                            if has_field_name and has_pos and has_rec:
                                                schema_table = table
                                                st.success(f"Found schema table: Table {table['table_num']} on Page {table['page']}")
                                                break

                                    if schema_table:
                                        df = pd.DataFrame(schema_table["data"])
                                        # Get the column indices for required fields - more flexible matching
                                        first_row = [str(cell).strip().upper() for cell in df.iloc[0]]
                                        
                                        field_name_idx = next(i for i, cell in enumerate(first_row) 
                                                            if 'FIELD' in str(cell).upper() and 'NAME' in str(cell).upper())
                                        pos_idx = next(i for i, cell in enumerate(first_row) 
                                                     if 'POS' in str(cell).upper())
                                        rec_idx = next(i for i, cell in enumerate(first_row) 
                                                     if 'REC' in str(cell).upper() and '#' in str(cell))
                                        
                                        # Create a new DataFrame with just the required columns
                                        new_df = pd.DataFrame({
                                            'Field Name': df.iloc[1:, field_name_idx],
                                            'Pos': df.iloc[1:, pos_idx],
                                            'Rec #': df.iloc[1:, rec_idx]
                                        })
                                        
                                        # Clean the DataFrame
                                        new_df = new_df[
                                            (new_df['Field Name'].notna()) &
                                            (new_df['Pos'].notna()) & 
                                            (new_df['Rec #'].notna()) &
                                            (new_df['Field Name'].str.strip() != '') &
                                            (new_df['Pos'].str.strip() != '') &
                                            (new_df['Rec #'].str.strip() != '')
                                        ].copy()  # Add .copy() to avoid SettingWithCopyWarning
                                        
                                        # Reset index after filtering
                                        new_df = new_df.reset_index(drop=True)
                                        
                                        # Display the processed data
                                        st.write("Schema Input Data:")
                                        st.dataframe(new_df)
                                        
                                        if not new_df.empty:
                                            try:
                                                # Generate schema
                                                schema_generator = SchemaGenerator(
                                                    entity=st.session_state.schema_config['entity'],
                                                    record_marker=st.session_state.schema_config['record_marker'],
                                                    domain_header=st.session_state.schema_config['domain_header'],
                                                    domain_trailer=st.session_state.schema_config['domain_trailer']
                                                )
                                                
                                                schema = schema_generator.generate_schema(new_df)
                                                
                                                if schema:
                                                    st.success("Schema generated successfully!")
                                                    
                                                    # Save schema
                                                    schema_path = "record_schema.yaml"
                                                    schema_generator.save_schema(schema, schema_path)
                                                    
                                                    # Display the generated schema
                                                    st.write("Generated Schema:")
                                                    st.json(schema)
                                                else:
                                                    st.error("Schema generation returned empty result")
                                            except Exception as e:
                                                st.error(f"Error in schema generation: {str(e)}")
                                                st.write("Debug - DataFrame content:")
                                                st.write(new_df.to_dict('records'))
                                        else:
                                            st.error("No valid data rows found in the processed table")
                                    else:
                                        st.error("Could not find a table with the required columns (Field Name, Pos, Rec #)")
                                        # Debug information for all tables
                                        st.write("Available tables:")
                                        for table in tables:
                                            df = pd.DataFrame(table["data"])
                                            st.write(f"Table {table['table_num']} on Page {table['page']}:")
                                            st.write("First row:", [str(cell).strip().upper() for cell in df.iloc[0]])
                                else:
                                    st.error("No tables found in the document")
                        
                        except Exception as e:
                            st.error(f"Error in schema generation: {str(e)}")

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
