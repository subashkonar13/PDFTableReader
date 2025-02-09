# PDFTablereader


A Python application that extracts tables from PDF files using Azure Document Intelligence (Form Recognizer) and generates structured schema files.

## Architecture Overview

```mermaid
graph TD
    A[PDF Upload] --> B[Streamlit UI]
    B --> C{Process PDF?}
    C -->|Yes| D[Azure Document Intelligence]
    D --> E[Table Extraction]
    E --> F[Excel Generation]
    F --> J[Download Excel]

```

## Module Description

### PDF Extractor App (`src/pdfreader.py`)
Main application entry point with Streamlit UI components:
- Handles file upload
- Provides configuration interface
- Manages PDF processing workflow
- Displays results and downloads


## Execution Flow

1. **PDF Upload and Configuration**
```mermaid
sequenceDiagram
    User->>Streamlit UI: Upload PDF
    User->>Streamlit UI: Configure Schema Settings
    Streamlit UI->>PDFProcessor: Process PDF
    PDFProcessor->>Azure AI: Send PDF
    Azure AI->>PDFProcessor: Return Tables
```

## Setup and Configuration

1. **Prerequisites**
   - Python >= 3.10
   - Docker (optional)
   - Azure Document Intelligence service

2. **Environment Setup**
   ```bash
   pip install -r requirements.txt
   ```

3. **Docker Build (Optional)**
   ```bash
   docker build -t pdf-extractor .
   docker run -p 8501:8501 pdf-extractor
   ```

## Usage

1. Start the application:
   ```bash
   python -m streamlit run src/pdfreader.py
   ```

2. Upload PDF and Process:
   - Upload PDF file
   - Click "Process PDF"
   - Download Excel and/or YAML schema


## Error Handling

The application includes comprehensive error handling for:
- PDF processing errors
- File handling problems
- Azure API communication errors
