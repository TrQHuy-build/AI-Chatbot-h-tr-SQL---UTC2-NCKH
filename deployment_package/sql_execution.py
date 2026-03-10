import sqlite3
import os
import sys

# Đảm bảo stdout hỗ trợ UTF-8 trên Windows
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

def create_sandbox(schema, data=None):
    """
    Tạo môi trường sandbox SQLite từ schema và dữ liệu mẫu.
    """
    conn = sqlite3.connect(":memory:")  # Tạo database trong bộ nhớ
    cursor = conn.cursor()

    # Tạo schema
    try:
        cursor.executescript(schema)
    except sqlite3.Error as e:
        conn.close()
        return None

    # Chèn dữ liệu mẫu (nếu có)
    if data:
        try:
            for table, rows in data.items():
                for row in rows:
                    placeholders = ", ".join(["?"] * len(row))
                    query = f"INSERT INTO {table} VALUES ({placeholders})"
                    cursor.execute(query, row)
            conn.commit()
        except sqlite3.Error as e:
            conn.close()
            return None

    return conn

def execute_query(conn, query):
    """
    Thực thi truy vấn SQL trên database sandbox.
    """
    cursor = conn.cursor()
    try:
        cursor.execute(query)
        results = cursor.fetchall()
        columns = [description[0] for description in cursor.description] if cursor.description else []
        return {"columns": columns, "results": results}
    except sqlite3.Error as e:
        return {"error": str(e)}

if __name__ == "__main__":
    # Ví dụ schema và dữ liệu mẫu
    schema = """
    CREATE TABLE students (
        id INTEGER PRIMARY KEY,
        name TEXT
    );
    CREATE TABLE courses (
        id INTEGER PRIMARY KEY,
        title TEXT
    );
    CREATE TABLE enrollments (
        student_id INTEGER,
        course_id INTEGER,
        FOREIGN KEY(student_id) REFERENCES students(id),
        FOREIGN KEY(course_id) REFERENCES courses(id)
    );
    """

    data = {
        "students": [(1, "Alice"), (2, "Bob")],
        "courses": [(1, "Database Systems"), (2, "Machine Learning")],
        "enrollments": [(1, 1), (2, 2)]
    }

    # Tạo sandbox
    conn = create_sandbox(schema, data)

    if conn:
        # Thực thi truy vấn SQL
        query = "SELECT students.name FROM students JOIN enrollments ON students.id = enrollments.student_id JOIN courses ON enrollments.course_id = courses.id WHERE courses.title = 'Database Systems';"
        result = execute_query(conn, query)

        # Hiển thị kết quả
        if "error" in result:
            print(f"Lỗi khi thực thi truy vấn: {result['error']}")
        else:
            print("Kết quả truy vấn:")
            print(" | ".join(result["columns"]))
            for row in result["results"]:
                print(" | ".join(map(str, row)))

        conn.close()