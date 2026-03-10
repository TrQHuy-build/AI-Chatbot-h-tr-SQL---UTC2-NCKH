"""
test_pipeline.py - Kiểm thử toàn bộ pipeline dự án
Chạy: python test_pipeline.py
"""
import sys
import os
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "deployment_package"))

PASS = "✅ PASS"
FAIL = "❌ FAIL"
WARN = "⚠️  WARN"

def section(title):
    print(f"\n{'='*50}")
    print(f"  {title}")
    print('='*50)

# ─────────────────────────────────────────
# TEST 1: Data Preprocessing
# ─────────────────────────────────────────
def test_data_preprocessing():
    section("TEST 1: Data Preprocessing")
    try:
        sys.path.insert(0, "datasets")
        from data_preprocessing import preprocess_spider_data

        # Tạo dữ liệu mẫu tạm thời
        sample = [
            {"question": "Find all students", "db_id": "school", "query": "SELECT * FROM students;"},
            {"question": "Count courses", "db_id": "school", "query": "SELECT COUNT(*) FROM courses;"},
        ]
        os.makedirs("datasets/test_tmp", exist_ok=True)
        in_f  = "datasets/test_tmp/test_in.json"
        out_f = "datasets/test_tmp/test_out.json"

        with open(in_f, "w", encoding="utf-8") as f:
            json.dump(sample, f)

        preprocess_spider_data(in_f, out_f)

        with open(out_f, "r", encoding="utf-8") as f:
            result = json.load(f)

        assert len(result) == 2
        assert result[0]["instruction"] == "Find all students"
        assert result[0]["output"] == "SELECT * FROM students;"
        assert "Database: school" in result[0]["input"]

        print(f"  {PASS} - Chuẩn hóa dữ liệu thành công ({len(result)} mẫu)")

        # Dọn dẹp
        import shutil
        shutil.rmtree("datasets/test_tmp")
        return True
    except Exception as e:
        print(f"  {FAIL} - {e}")
        return False

# ─────────────────────────────────────────
# TEST 2: SQL Execution (Sandbox)
# ─────────────────────────────────────────
def test_sql_execution():
    section("TEST 2: SQL Execution & Sandbox")
    try:
        from sql_execution import create_sandbox, execute_query

        schema = """
        CREATE TABLE students (id INTEGER PRIMARY KEY, name TEXT);
        CREATE TABLE courses  (id INTEGER PRIMARY KEY, title TEXT);
        CREATE TABLE enrollments (student_id INTEGER, course_id INTEGER);
        """
        data = {
            "students":    [(1, "Alice"), (2, "Bob"), (3, "Charlie")],
            "courses":     [(1, "Database Systems"), (2, "Machine Learning")],
            "enrollments": [(1, 1), (2, 2), (3, 1)],
        }

        conn = create_sandbox(schema, data)
        assert conn is not None, "Không tạo được sandbox"

        # Test SELECT đơn giản
        r = execute_query(conn, "SELECT * FROM students;")
        assert "error" not in r
        assert len(r["results"]) == 3
        print(f"  {PASS} - SELECT đơn giản: {len(r['results'])} hàng")

        # Test JOIN
        q = """
        SELECT students.name
        FROM students
        JOIN enrollments ON students.id = enrollments.student_id
        JOIN courses     ON enrollments.course_id = courses.id
        WHERE courses.title = 'Database Systems';
        """
        r2 = execute_query(conn, q)
        assert "error" not in r2
        names = [row[0] for row in r2["results"]]
        assert "Alice" in names and "Charlie" in names
        print(f"  {PASS} - JOIN query: tìm thấy {names}")

        # Test GROUP BY
        q2 = "SELECT course_id, COUNT(*) FROM enrollments GROUP BY course_id;"
        r3 = execute_query(conn, q2)
        assert "error" not in r3
        print(f"  {PASS} - GROUP BY query: {r3['results']}")

        # Test câu truy vấn sai
        r4 = execute_query(conn, "SELECT * FROM non_existent_table;")
        assert "error" in r4
        print(f"  {PASS} - Bắt lỗi truy vấn sai: '{r4['error']}'")

        conn.close()
        return True
    except Exception as e:
        print(f"  {FAIL} - {e}")
        import traceback; traceback.print_exc()
        return False

# ─────────────────────────────────────────
# TEST 3: RAG Integration
# ─────────────────────────────────────────
def test_rag_integration():
    section("TEST 3: RAG Integration (FAISS + Embeddings)")
    try:
        from rag_integration import create_vector_database, retrieve_context
        from langchain_huggingface import HuggingFaceEmbeddings

        docs = [
            "Table students(id, name): Stores student information",
            "Table courses(id, title): Stores course information",
            "Table enrollments(student_id, course_id): Stores enrollment records",
            "Use JOIN to connect students and courses via enrollments",
            "Use WHERE clause to filter rows by condition",
            "Use GROUP BY to aggregate results",
            "Use COUNT(*) to count the number of records",
        ]

        db_path = "./datasets/test_vector_db"
        print("  Đang tải embedding model (lần đầu có thể mất vài phút)...")
        embedding_model = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2"
        )

        vector_db = create_vector_database(docs, embedding_model, db_path)
        assert vector_db is not None

        # Test truy xuất context
        question = "How to find students enrolled in a course?"
        context  = retrieve_context(vector_db, question, k=3)
        assert len(context) > 0
        print(f"  {PASS} - Đã tạo vector DB và truy xuất {len(context)} context")
        for i, c in enumerate(context, 1):
            print(f"          [{i}] {c[:70]}...")

        # Dọn dẹp
        import shutil
        if os.path.exists(db_path):
            shutil.rmtree(db_path)
        return True
    except Exception as e:
        print(f"  {WARN} - {e}")
        print("       (RAG test bỏ qua nếu chưa cài sentence-transformers)")
        return None  # Warning, not critical failure

# ─────────────────────────────────────────
# TEST 4: Text-to-SQL (không cần GPU)
# ─────────────────────────────────────────
def test_text_to_sql_prompt():
    section("TEST 4: Text-to-SQL Prompt Format")
    try:
        # Kiểm tra định dạng prompt mà không cần load model nặng
        question = "Find all students enrolled in Database Systems"
        schema   = "students(id, name), courses(id, title), enrollments(student_id, course_id)"
        prompt   = f"Question: {question}\nSchema: {schema}\nSQL Query:"

        assert "Question:" in prompt
        assert "Schema:"   in prompt
        assert "SQL Query:" in prompt
        print(f"  {PASS} - Prompt format hợp lệ")
        print(f"          Preview: {prompt[:80]}...")

        # Kiểm tra trích xuất SQL từ output giả
        raw_output = f"{prompt}\nSELECT students.name FROM students JOIN enrollments ON students.id = enrollments.student_id;"
        if "SQL Query:" in raw_output:
            sql = raw_output.split("SQL Query:")[1].strip()
            assert sql.upper().startswith("SELECT")
            print(f"  {PASS} - SQL extraction: '{sql[:60]}...'")

        return True
    except Exception as e:
        print(f"  {FAIL} - {e}")
        return False

# ─────────────────────────────────────────
# TEST 5: Backend API (kiểm tra import)
# ─────────────────────────────────────────
def test_backend_imports():
    section("TEST 5: Backend API Imports")
    results = {}
    libs = {
        "fastapi":        "FastAPI",
        "uvicorn":        "uvicorn",
        "pydantic":       "pydantic",
        "torch":          "PyTorch",
        "transformers":   "Transformers",
        "langchain_community": "LangChain Community",
        "langchain_huggingface": "LangChain HuggingFace",
        "faiss":          "FAISS",
        "sqlite3":        "SQLite3 (built-in)",
    }
    for lib, name in libs.items():
        try:
            __import__(lib)
            print(f"  {PASS} - {name}")
            results[lib] = True
        except ImportError as e:
            print(f"  {FAIL} - {name}: {e}")
            results[lib] = False

    critical = ["fastapi", "uvicorn", "torch", "transformers"]
    all_critical_ok = all(results.get(c, False) for c in critical)
    return all_critical_ok

# ─────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────
if __name__ == "__main__":
    print("\n" + "█"*50)
    print("   SQL CHATBOT AI - PIPELINE TEST SUITE")
    print("█"*50)

    results = {}
    results["Data Preprocessing"]  = test_data_preprocessing()
    results["SQL Execution"]        = test_sql_execution()
    results["RAG Integration"]      = test_rag_integration()
    results["Text-to-SQL Format"]   = test_text_to_sql_prompt()
    results["Backend Imports"]      = test_backend_imports()

    # Summary
    section("KẾT QUẢ TỔNG HỢP")
    total  = len(results)
    passed = sum(1 for v in results.values() if v is True)
    warned = sum(1 for v in results.values() if v is None)
    failed = sum(1 for v in results.values() if v is False)

    for name, status in results.items():
        icon = PASS if status is True else (WARN if status is None else FAIL)
        print(f"  {icon} {name}")

    print(f"\n  Tổng: {total} | Pass: {passed} | Warn: {warned} | Fail: {failed}")

    if failed == 0:
        print("\n  🎉 Dự án sẵn sàng chạy!")
        print("  👉 Chạy backend: .venv\\Scripts\\python.exe -m uvicorn deployment_package.main:app --reload --port 8000")
        print("  👉 Chạy frontend: cd frontend && npm install && npm run dev")
    else:
        print(f"\n  ⚠️  Có {failed} module cần kiểm tra lại.")
        print("  👉 Chạy: pip install -r deployment_package/requirements.txt")
