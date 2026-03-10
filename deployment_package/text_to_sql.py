import os
from transformers import AutoModelForCausalLM, AutoTokenizer
import torch

def load_model(model_dir):
    """
    Tải mô hình đã fine-tune từ thư mục lưu trữ.
    """
    print("Đang tải mô hình Text-to-SQL...")
    
    # Nếu mô hình đã fine-tune không tồn tại, sử dụng mô hình Phi-2 mặc định
    if not os.path.exists(model_dir):
        model_name = "microsoft/phi-2"
    else:
        model_name = model_dir
    
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
        device_map="auto"
    )
    print("Mô hình đã được tải thành công.")
    return model, tokenizer

def generate_sql_query(model, tokenizer, question, schema):
    """
    Sinh truy vấn SQL từ câu hỏi và schema.
    """
    # Tạo prompt cho mô hình
    prompt = f"Question: {question}\nSchema: {schema}\nSQL Query:"

    # Sinh truy vấn SQL
    print("Đang sinh truy vấn SQL...")
    inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
    
    outputs = model.generate(
        **inputs,
        max_new_tokens=256,
        do_sample=True,
        top_k=50,
        top_p=0.95,
        temperature=0.7
    )

    # Giải mã đầu ra
    sql_query = tokenizer.decode(outputs[0], skip_special_tokens=True)
    
    # Trích xuất phần SQL từ đầu ra
    if "SQL Query:" in sql_query:
        sql_query = sql_query.split("SQL Query:")[1].strip()
    
    return sql_query

if __name__ == "__main__":
    # Đường dẫn mô hình đã fine-tune
    model_dir = "./model_weights"

    # Tải mô hình
    model, tokenizer = load_model(model_dir)

    # Ví dụ câu hỏi và schema
    question = "Find names of all students enrolled in 'Database Systems' course"
    schema = "Tables: students(id, name), courses(id, title), enrollments(student_id, course_id)"

    # Sinh truy vấn SQL
    sql_query = generate_sql_query(model, tokenizer, question, schema)
    print("Generated SQL Query:")
    print(sql_query)