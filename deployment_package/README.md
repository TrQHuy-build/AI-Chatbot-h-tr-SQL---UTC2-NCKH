# Text-to-SQL Chatbot System

This project implements a high-performance Text-to-SQL chatbot using a fine-tuned Phi-3 model, RAG-based schema retrieval with FAISS, and a secure SQL execution sandbox.

## Architecture
The system follows a decoupled architecture:
1. **Frontend (NextJS/React)**: Captures user questions and displays query results.
2. **Backend (FastAPI)**: Orchestrates the pipeline.
3. **Schema RAG (FAISS)**: Dynamically retrieves relevant table schemas based on the user's question to keep prompts concise.
4. **LLM (Phi-3 Mini)**: Fine-tuned with Unsloth (LoRA) to generate precise SQLite queries from natural language and schema context.
5. **Execution Sandbox**: An in-memory SQLite database that safely executes generated SQL and returns structured JSON data.

## Environment Setup
- **Python Version**: 3.10 or higher is required.
- **Hardware**: An NVIDIA GPU (T4, L4, or A100) is mandatory for efficient fine-tuning and inference using the Unsloth library.
- **Dependencies**: Install core libraries using:
  ```bash
  pip install unsloth langchain-community langchain-huggingface faiss-cpu fastapi uvicorn
  ```

## API Documentation
### POST `/query`
Processes a natural language question and returns the SQL and execution results.

**Request Body:**
```json
{
  "question": "Who is the manager of the Engineering department?"
}
```

**Response Body:**
```json
{
  "status": "success",
  "question": "Who is the manager of the Engineering department?",
  "sql": "SELECT manager_id FROM Departments WHERE name = 'Engineering';",
  "schema_used": "Table: Departments (...)",
  "data": [ { "manager_id": 101 } ]
}
```

## Frontend Integration
To connect the NextJS frontend:
1. Create a `.env.local` file:
   ```bash
   NEXT_PUBLIC_API_URL=http://your-backend-ip:8000
   ```
2. Implementation example:
   ```javascript
   const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/query`, {
     method: 'POST',
     headers: { 'Content-Type': 'application/json' },
     body: JSON.stringify({ question: userQuestion }),
   });
   const result = await response.json();
   ```

## Deployment
### Docker
Build and run the container using the provided Dockerfile:
```bash
docker build -t text2sql-backend .
docker run -p 8000:8000 text2sql-backend
```

### Hugging Face Spaces
1. Create a new Space with the **Docker SDK**.
2. Ensure the container exposes port **7860** (update `EXPOSE` and `uvicorn` port in Dockerfile).
3. Select a GPU instance in settings to enable Unsloth-based inference.
