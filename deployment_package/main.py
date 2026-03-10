import os
import sys
import torch
import sqlite3
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from transformers import AutoModelForCausalLM, AutoTokenizer

# Thêm deployment_package vào sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sql_execution import create_sandbox, execute_query

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── Cấu hình model ──────────────────────────────────────────────────
# DEV_MODE=true  → dùng mock SQL (không tải model nặng)
# DEV_MODE=false → tải model thật từ HuggingFace hoặc model_weights/
DEV_MODE = os.environ.get("DEV_MODE", "true").lower() == "true"

MODEL_DIR  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "model_weights")
MODEL_NAME = "microsoft/phi-2"   # fallback nếu chưa có fine-tuned weights

tokenizer = None
model     = None

# ── Default SQL sandbox schema ───────────────────────────────────────
DEFAULT_SCHEMA_SQL = """
CREATE TABLE students    (id INTEGER PRIMARY KEY, name TEXT, gpa REAL);
CREATE TABLE courses     (id INTEGER PRIMARY KEY, title TEXT, credits INTEGER);
CREATE TABLE enrollments (student_id INTEGER, course_id INTEGER,
                          grade TEXT,
                          FOREIGN KEY(student_id) REFERENCES students(id),
                          FOREIGN KEY(course_id)  REFERENCES courses(id));
"""
DEFAULT_DATA = {
    "students":    [(1,"Alice",3.8),(2,"Bob",3.2),(3,"Charlie",3.9),(4,"Diana",2.8)],
    "courses":     [(1,"Database Systems",3),(2,"Machine Learning",3),(3,"Algorithms",3)],
    "enrollments": [(1,1,"A"),(2,2,"B"),(3,1,"A"),(4,3,"C"),(1,2,"B")],
}

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load model khi startup."""
    global model, tokenizer
    if DEV_MODE:
        logger.info("🚀 DEV_MODE=true — chạy không cần model (mock SQL)")
    else:
        logger.info(f"📥 Đang tải model: {MODEL_NAME if not os.path.exists(MODEL_DIR) else MODEL_DIR}")
        _name = MODEL_DIR if (os.path.exists(MODEL_DIR) and len(os.listdir(MODEL_DIR)) > 0) else MODEL_NAME
        tokenizer = AutoTokenizer.from_pretrained(_name, trust_remote_code=True)
        model = AutoModelForCausalLM.from_pretrained(
            _name,
            dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
            device_map="auto",
            trust_remote_code=True,
        )
        logger.info("✅ Model đã sẵn sàng")
    yield

# ── FastAPI app ───────────────────────────────────────────────────────
app = FastAPI(
    title="SQL Chatbot AI",
    description="Chatbot hỗ trợ gợi ý giải bài tập SQL bằng Phi-3",
    version="1.0.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

# ── Schemas ───────────────────────────────────────────────────────────
class QueryRequest(BaseModel):
    question: str
    db_schema: str = "students(id, name), courses(id, title), enrollments(student_id, course_id)"

class QueryResponse(BaseModel):
    status: str
    sql_query: str = ""
    execution_result: str = ""
    error: str = ""

# ── Helpers ───────────────────────────────────────────────────────────
def _parse_schema(schema_str: str) -> dict:
    """
    Phân tích schema string thành dict: { table_name: [col1, col2, ...] }
    Hỗ trợ: "students(id, name, gpa), courses(id, title)"
    """
    import re
    tables = {}
    # Tìm tất cả pattern: table_name(col1, col2, ...)
    for match in re.finditer(r'(\w+)\s*\(([^)]+)\)', schema_str):
        tname = match.group(1).lower()
        cols  = [c.strip().lower() for c in match.group(2).split(',')]
        tables[tname] = cols
    return tables

def _detect_table(q: str, tables: dict) -> str:
    """Tìm bảng phù hợp nhất dựa trên câu hỏi."""
    # Map từ khóa → tên bảng
    keywords = {
        "student": ["student", "sinh viên", "học sinh", "sv"],
        "course":  ["course", "khóa học", "môn học", "lớp học"],
        "enroll":  ["enroll", "đăng ký", "tham gia", "registration"],
        "product": ["product", "sản phẩm", "hàng hóa"],
        "order":   ["order", "đơn hàng", "đặt hàng"],
        "employee":["employee", "nhân viên", "staff"],
        "department":["department", "phòng ban"],
    }
    q_lower = q.lower()
    for tname in tables:
        # Nếu tên bảng xuất hiện trực tiếp trong câu hỏi
        if tname in q_lower:
            return tname
        # Tìm qua keyword map
        for key, synonyms in keywords.items():
            if key in tname and any(s in q_lower for s in synonyms):
                return tname
    # Fallback: bảng đầu tiên
    return list(tables.keys())[0] if tables else "unknown"

def _extract_number(q: str):
    """Trích xuất số trong câu hỏi. VD: 'tuổi lớn hơn 20' → 20"""
    import re
    nums = re.findall(r'\b\d+(?:\.\d+)?\b', q)
    return nums[0] if nums else None

def _detect_condition_col(q: str, cols: list):
    """Tìm cột phù hợp để đặt điều kiện WHERE dựa trên câu hỏi.
    Ưu tiên 1: match qua keyword map (ngữ nghĩa).
    Ưu tiên 2: tên cột xuất hiện như từ độc lập trong câu hỏi đã bỏ phần schema.
    """
    import re
    q_lower = q.lower()
    # Loại bỏ phần schema trong ngoặc đơn khỏi câu hỏi để tránh false-positive
    q_no_schema = re.sub(r'\w+\s*\([^)]*\)', '', q_lower).strip()

    col_keywords = {
        "age":    ["tuổi", "age", "years old", "tuoi", "nam tuoi"],
        "gpa":    ["gpa", "điểm", "diem", "grade point", "academic"],
        "salary": ["lương", "luong", "salary", "thu nhập", "thu nhap", "income", "wage"],
        "price":  ["giá", "gia", "price", "cost", "phi"],
        "name":   ["tên người", "ho ten", "full name"],   # loại "ten" chung để tránh match nhầm
        "title":  ["tiêu đề", "title"],
        "major":  ["ngành", "nganh", "major", "chuyên ngành", "chuyen nganh", "field"],
        "gender": ["giới tính", "gioi tinh", "gender", "sex"],
        "city":   ["thành phố", "thanh pho", "city", "địa chỉ", "dia chi", "location"],
        "year":   ["năm", "year"],
        "credits":["tín chỉ", "tin chi", "credits", "credit"],
        "grade":  ["điểm chữ", "grade", "diem chu", "xep loai"],
        "department": ["phòng ban", "phong ban", "department", "dept", "bo phan"],
    }
    # Ưu tiên 1: keyword map (ngữ nghĩa cao nhất)
    for col in cols:
        col_l = col.lower()
        for key, synonyms in col_keywords.items():
            if key in col_l and any(s in q_lower for s in synonyms):
                return col
    # Ưu tiên 2: tên cột xuất hiện như từ độc lập trong câu hỏi (đã loại phần schema)
    # Bỏ qua cột id và cột có tên quá ngắn (≤1 ký tự)
    for col in cols:
        col_l = col.lower()
        if col_l in ("id",) or col_l.endswith("id") or len(col_l) <= 1:
            continue
        if re.search(r'\b' + re.escape(col_l) + r'\b', q_no_schema):
            return col
    return None

def _detect_operator(q: str) -> tuple:
    """Nhận dạng toán tử so sánh. Trả về (operator, value_str).
    Thứ tự pattern: BETWEEN → >= → <= → < (nho hon trước) → > (lon hon/hon sau) → =
    Quan trọng: 'nho hon' phải nằm trước pattern 'hon' để không bị false-positive.
    """
    import re
    q_l = q.lower()
    patterns = [
        # 1. BETWEEN
        (r'(?:between|từ|tu)\s*(\d+(?:\.\d+)?)\s*(?:to|đến|den|và|va|and)\s*(\d+(?:\.\d+)?)', "BETWEEN"),
        # 2. >= (lon hon hoac bang / at least)
        (r'(?:lớn hơn hoặc bằng|lon hon hoac bang|>=|at least|ít nhất|it nhat)\s*(\d+(?:\.\d+)?)', ">="),
        # 3. <= (nho hon hoac bang / at most)
        (r'(?:nhỏ hơn hoặc bằng|nho hon hoac bang|<=|at most|nhiều nhất|nhieu nhat)\s*(\d+(?:\.\d+)?)', "<="),
        # 4. < — "nho hon" PHẢI đứng TRƯỚC pattern "hon" ở dòng dưới
        (r'(?:nhỏ hơn|nho hon|less than|younger than|fewer than|thấp hơn|thap hon|dưới|duoi|below)\s*(\d+(?:\.\d+)?)', "<"),
        # 5. > — "lon hon" và "hon" (đứng SAU để không match "nho hon")
        (r'(?:lớn hơn|lon hon|greater than|older than|more than|cao hơn|cao hon|trên|tren|above)\s*(\d+(?:\.\d+)?)', ">"),
        (r'(?:hơn|hon)\s*(\d+(?:\.\d+)?)', ">"),
        # 6. =
        (r'(?:=|bằng|bang|equal|exactly|là|la)\s*(\d+(?:\.\d+)?)', "="),
        # 7. plain ký tự
        (r'>\s*(\d+(?:\.\d+)?)', ">"),
        (r'<\s*(\d+(?:\.\d+)?)', "<"),
    ]
    for pattern, op in patterns:
        m = re.search(pattern, q_l)
        if m:
            if op == "BETWEEN":
                return ("BETWEEN", f"{m.group(1)} AND {m.group(2)}")
            return (op, m.group(1))
    return (None, None)

def _generate_sql_smart(question: str, schema: str) -> str:
    """
    Smart SQL generator:
    - Phân tích schema động
    - Nhận dạng ý định câu hỏi (SELECT, WHERE, COUNT, JOIN, GROUP BY, ORDER BY)
    - Sinh SQL đúng cú pháp, không có comment
    """
    q      = question.lower()
    tables = _parse_schema(schema)

    if not tables:
        return "SELECT 'Schema không hợp lệ' AS error;"

    main_table = _detect_table(q, tables)
    cols       = tables.get(main_table, ["*"])
    alias      = main_table[0]  # VD: students → s

    # ── 1. COUNT ─────────────────────────────────────────────────────
    if any(k in q for k in ["đếm", "count", "bao nhiêu", "how many", "số lượng", "tổng số"]):
        cond_col = _detect_condition_col(q, cols)
        op, val  = _detect_operator(q)
        if cond_col and op and val:
            return (
                f"SELECT COUNT(*) AS total\n"
                f"FROM {main_table}\n"
                f"WHERE {cond_col} {op} {val};"
            )
        return f"SELECT COUNT(*) AS total FROM {main_table};"

    # ── 2. WHERE / LỌC ĐIỀU KIỆN ────────────────────────────────────
    filter_kws = ["lọc", "loc", "filter", "tìm", "tim", "find", "where",
                  "điều kiện", "dieu kien", "condition",
                  "lớn hơn", "lon hon", "nhỏ hơn", "nho hon",
                  "bằng", "bang", "equal", "exactly",
                  "greater", "less", "older", "younger",
                  "between", "có tuổi", "co tuoi", "có gpa", "co gpa",
                  "có lương", "co luong", "có điểm", "co diem",
                  "danh sách", "danh sach"]
    if any(k in q for k in filter_kws):
        cond_col = _detect_condition_col(q, cols)
        op, val  = _detect_operator(q)
        select_cols = ", ".join(cols) if cols != ["*"] else "*"
        if cond_col and op and val:
            if op == "BETWEEN":
                return (
                    f"SELECT {select_cols}\n"
                    f"FROM {main_table}\n"
                    f"WHERE {cond_col} BETWEEN {val};"
                )
            return (
                f"SELECT {select_cols}\n"
                f"FROM {main_table}\n"
                f"WHERE {cond_col} {op} {val};"
            )
        # Có filter nhưng không nhận ra điều kiện → SELECT tất cả
        return f"SELECT {select_cols} FROM {main_table};"

    # ── 3. JOIN ──────────────────────────────────────────────────────
    join_kws = ["join", "kết hợp", "ket hop", "liên kết", "lien ket",
                "đăng ký", "dang ky", "enroll", "tham gia", "tham"]
    if any(k in q for k in join_kws) and len(tables) >= 2:
        tlist = list(tables.keys())
        t1, t2 = tlist[0], tlist[1]
        a1, a2 = t1[0], t2[0]
        c1     = tables[t1]
        c2     = tables[t2]
        # Tìm cột khoá ngoại
        fk = next((c for c in c1 if t2.rstrip('s') in c or "id" in c and c != "id"), c1[0])
        return (
            f"SELECT {a1}.{c1[1] if len(c1)>1 else c1[0]}, "
            f"{a2}.{c2[1] if len(c2)>1 else c2[0]}\n"
            f"FROM {t1} {a1}\n"
            f"JOIN {t2} {a2} ON {a1}.id = {a2}.{fk};"
        )

    # ── 4. GROUP BY ──────────────────────────────────────────────────
    group_kws = ["group", "nhóm", "nhom", "theo từng", "theo tung",
                 "per", "mỗi", "moi", "thống kê", "thong ke", "statistics"]
    if any(k in q for k in group_kws):
        # Tìm cột nhóm: tìm qua keyword map trước, rồi fallback cột không phải id
        group_col = _detect_condition_col(q, cols)
        if not group_col:
            # Fallback: cột đầu tiên không phải id
            group_col = next(
                (c for c in cols if not c.lower().endswith("id") and c.lower() != "id"),
                cols[0]
            )
        return (
            f"SELECT {group_col}, COUNT(*) AS total\n"
            f"FROM {main_table}\n"
            f"GROUP BY {group_col};"
        )

    # ── 5. ORDER BY / SẮP XẾP ───────────────────────────────────────
    order_kws  = ["sắp xếp", "sap xep", "sort", "order", "top",
                  "cao nhất", "cao nhat", "thấp nhất", "thap nhat",
                  "lớn nhất", "lon nhat", "nhỏ nhất", "nho nhat",
                  "highest", "lowest", "best", "xep hang", "xếp hạng"]
    if any(k in q for k in order_kws):
        sort_col   = _detect_condition_col(q, cols) or (cols[1] if len(cols) > 1 else cols[0])
        direction  = "ASC" if any(k in q for k in ["tăng", "asc", "thấp nhất", "lowest"]) else "DESC"
        num        = _extract_number(q)
        limit_sql  = f"\nLIMIT {num}" if num and int(float(num)) < 1000 else ""
        select_cols = ", ".join(cols)
        return (
            f"SELECT {select_cols}\n"
            f"FROM {main_table}\n"
            f"ORDER BY {sort_col} {direction}{limit_sql};"
        )

    # ── 6. SELECT ALL (mặc định) ──────────────────────────────────────
    select_cols = ", ".join(cols) if cols != ["*"] else "*"
    return f"SELECT {select_cols} FROM {main_table};"

def _generate_sql_model(question: str, schema: str) -> str:
    """Sinh SQL từ model thật."""
    prompt = (
        f"### Instruction:\nConvert the question to SQL.\n\n"
        f"### Schema:\n{schema}\n\n"
        f"### Question:\n{question}\n\n"
        f"### SQL Query:\n"
    )
    inputs  = tokenizer(prompt, return_tensors="pt").to(model.device)
    outputs = model.generate(
        **inputs, max_new_tokens=200,
        do_sample=False, temperature=1.0,
        pad_token_id=tokenizer.eos_token_id,
    )
    decoded = tokenizer.decode(outputs[0], skip_special_tokens=True)
    if "### SQL Query:" in decoded:
        sql = decoded.split("### SQL Query:")[-1].strip()
        # Lấy chỉ câu lệnh đầu tiên
        sql = sql.split(";")[0].strip() + ";"
        return sql
    return decoded.strip()

def _format_result(result: dict) -> str:
    """Định dạng kết quả truy vấn thành chuỗi dễ đọc."""
    if "error" in result:
        return f"❌ Lỗi: {result['error']}"
    cols = result.get("columns", [])
    rows = result.get("results", [])
    if not rows:
        return "⚠️ Không có kết quả"
    header = " | ".join(cols)
    sep    = "-" * len(header)
    lines  = [header, sep] + [" | ".join(str(v) for v in row) for row in rows]
    return "\n".join(lines)

def _build_dynamic_sandbox(tables: dict):
    """
    Tự động tạo CREATE TABLE và dữ liệu mẫu từ schema người dùng nhập.
    Nhận dạng kiểu dữ liệu cột theo tên: *id→INTEGER PK, age/gpa/salary/…→REAL, còn lại→TEXT.
    Cột FK (dạng xxx_id) được tạo là INTEGER (không phải PK) và điền giá trị 1..5.
    """

    def _col_type(col: str, is_first: bool) -> str:
        col_l = col.lower()
        # Cột đầu tiên tên là 'id' hoặc chính xác là '<table>id' → PK
        if is_first and (col_l == "id" or col_l in ("studentid","courseid","empid","productid")):
            return "INTEGER PRIMARY KEY"
        # Cột FK dạng xxx_id hoặc xxxid (không phải PK)
        if col_l.endswith("_id") or (col_l.endswith("id") and not is_first):
            return "INTEGER"
        if any(k in col_l for k in ["age","year","gpa","salary","price","score","credits","qty","quantity"]):
            return "REAL"
        return "TEXT"

    def _sample_value(col: str, row_idx: int):
        col_l = col.lower()
        # FK columns: giá trị 1..5 tuần hoàn
        if col_l.endswith("_id") or (col_l.endswith("id") and col_l not in ("id","studentid","courseid","empid")):
            return ((row_idx - 1) % 5) + 1
        # PK / id
        if col_l == "id" or col_l in ("studentid","courseid","empid","productid"):
            return row_idx
        if "name" in col_l:
            return ["Alice","Bob","Charlie","Diana","Eve","Frank","Grace","Henry"][(row_idx - 1) % 8]
        if "title" in col_l or "course" in col_l:
            return ["Database Systems","Machine Learning","Algorithms","OS","Networks","Math"][(row_idx - 1) % 6]
        if "age" in col_l:
            return 18 + (row_idx * 2) % 20
        if "gpa" in col_l:
            return round(2.0 + (row_idx * 0.4) % 2, 1)
        if "salary" in col_l:
            return 3000000 + row_idx * 500000
        if "major" in col_l:
            return ["Computer Science","Information Technology","Data Science","Software Engineering"][(row_idx - 1) % 4]
        if "gender" in col_l or "sex" in col_l:
            return "Male" if row_idx % 2 == 1 else "Female"
        if "city" in col_l or "address" in col_l:
            return ["Hanoi","Ho Chi Minh","Da Nang","Can Tho"][(row_idx - 1) % 4]
        if "grade" in col_l:
            return ["A","B","C","D","F"][(row_idx - 1) % 5]
        if "credits" in col_l:
            return [2, 3, 4][(row_idx - 1) % 3]
        if "price" in col_l or "cost" in col_l:
            return round(10.0 + row_idx * 5.5, 2)
        if "department" in col_l or "dept" in col_l:
            return f"Department_{row_idx}"
        return f"{col.capitalize()}_{row_idx}"

    schema_sql_parts = []
    data = {}
    NUM_ROWS = 5

    for tname, cols in tables.items():
        col_defs = ", ".join(
            f"{c} {_col_type(c, i == 0)}" for i, c in enumerate(cols)
        )
        schema_sql_parts.append(f"CREATE TABLE IF NOT EXISTS {tname} ({col_defs});")
        data[tname] = [tuple(_sample_value(c, i) for c in cols) for i in range(1, NUM_ROWS + 1)]

    return "\n".join(schema_sql_parts), data

# ── Endpoints ─────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    return {
        "status": "ok",
        "dev_mode": DEV_MODE,
        "model_loaded": model is not None,
        "gpu": torch.cuda.is_available(),
    }

@app.post("/query", response_model=QueryResponse)
async def query(req: QueryRequest):
    """
    Nhận câu hỏi ngôn ngữ tự nhiên → sinh SQL → thực thi sandbox → trả kết quả.
    """
    try:
        logger.info(f"Query: {req.question}")

        # 1. Sinh SQL
        sql = _generate_sql_smart(req.question, req.db_schema) if DEV_MODE \
              else _generate_sql_model(req.question, req.db_schema)

        # 2. Xây dựng sandbox từ schema người dùng nhập (nếu khác default)
        user_tables = _parse_schema(req.db_schema)
        use_default = set(user_tables.keys()) == set(["students","courses","enrollments"])

        if use_default:
            conn = create_sandbox(DEFAULT_SCHEMA_SQL, DEFAULT_DATA)
        else:
            # Tạo sandbox động từ schema người dùng + dữ liệu mẫu tự động
            dynamic_schema_sql, dynamic_data = _build_dynamic_sandbox(user_tables)
            conn = create_sandbox(dynamic_schema_sql, dynamic_data)
        result = execute_query(conn, sql) if conn else {"error": "Không tạo được sandbox"}
        conn.close() if conn else None

        exec_str = _format_result(result)

        return QueryResponse(
            status="success",
            sql_query=sql,
            execution_result=exec_str,
        )
    except Exception as e:
        logger.error(f"Error: {e}")
        return QueryResponse(status="error", error=str(e))

@app.get("/")
async def root():
    return {"message": "SQL Chatbot AI đang chạy. Truy cập /docs để xem API."}
