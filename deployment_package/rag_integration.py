import os
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.documents import Document
from transformers import AutoModelForCausalLM, AutoTokenizer
import torch

def create_vector_database(documents_text, embedding_model, db_path):
    """
    Tạo vector database từ tài liệu và lưu trữ bằng FAISS.
    """
    os.makedirs(db_path, exist_ok=True)
    
    if os.path.exists(os.path.join(db_path, "index.faiss")):
        print("Vector database đã tồn tại. Đang tải...")
        return FAISS.load_local(db_path, embedding_model, allow_dangerous_deserialization=True)

    print("Đang tạo vector database...")
    
    # Chuyển đổi tài liệu thành Document objects
    documents = [Document(page_content=text) for text in documents_text]
    
    vector_db = FAISS.from_documents(documents, embedding_model)
    vector_db.save_local(db_path)
    print("Vector database đã được lưu tại:", db_path)
    return vector_db

def retrieve_context(vector_db, question, k=3):
    """
    Truy xuất context từ vector database.
    """
    retriever = vector_db.as_retriever(search_type="similarity", search_kwargs={"k": k})
    results = retriever.invoke(question)
    return [doc.page_content for doc in results]

if __name__ == "__main__":
    # Tài liệu mẫu
    documents = [
        "Table students(id, name): Store student information",
        "Table courses(id, title): Store course information",
        "Table enrollments(student_id, course_id): Store enrollment information",
        "To find students in a course, join students, enrollments, and courses tables",
        "Use WHERE clause to filter by course title"
    ]

    # Đường dẫn lưu trữ vector database
    db_path = "./datasets/vector_db"

    # Tải mô hình embedding
    embedding_model = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")

    # Tạo hoặc tải vector database
    vector_db = create_vector_database(documents, embedding_model, db_path)

    # Câu hỏi mẫu
    question = "How to find students in Database Systems course?"

    # Truy xuất context
    context = retrieve_context(vector_db, question)
    print("Retrieved Context:")
    for i, doc in enumerate(context, 1):
        print(f"{i}. {doc}")