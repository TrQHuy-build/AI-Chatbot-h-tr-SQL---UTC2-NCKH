import json
import os
import requests
import zipfile

def download_and_extract_spider_dataset(url, extract_to):
    """
    Tải và giải nén Spider dataset từ URL.
    """
    zip_path = os.path.join(extract_to, "spider.zip")

    # Tạo thư mục nếu chưa tồn tại
    os.makedirs(extract_to, exist_ok=True)

    # Tải file zip
    print("Đang tải Spider dataset...")
    try:
        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status()
        with open(zip_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=1024):
                if chunk:
                    f.write(chunk)

        # Giải nén file zip
        print("Đang giải nén Spider dataset...")
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            zip_ref.extractall(extract_to)

        # Xóa file zip sau khi giải nén
        os.remove(zip_path)
        print("Hoàn tất tải và giải nén Spider dataset.")
    except Exception as e:
        print(f"Lỗi khi tải dataset: {e}")
        if os.path.exists(zip_path):
            os.remove(zip_path)
        return False
    return True

def preprocess_spider_data(input_file, output_file):
    """
    Đọc dữ liệu từ Spider dataset, chuẩn hóa và lưu vào file đầu ra theo định dạng instruction tuning.
    """
    processed_data = []

    # Đọc dữ liệu từ file đầu vào
    with open(input_file, 'r', encoding='utf-8') as f:
        raw_data = json.load(f)

    # Chuẩn hóa dữ liệu
    for item in raw_data:
        instruction = item.get('question', '')
        input_context = f"Database: {item.get('db_id', '')}"
        output_sql = item.get('query', '')

        processed_data.append({
            "instruction": instruction,
            "input": input_context,
            "output": output_sql
        })

    # Lưu dữ liệu đã chuẩn hóa vào file đầu ra
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(processed_data, f, ensure_ascii=False, indent=4)

if __name__ == "__main__":
    # URL của Spider dataset
    spider_url = "https://yale-lily.github.io/spider/spider.zip"
    # Tự động xác định đường dẫn tuyệt đối của thư mục hiện tại
    base_dir = os.path.dirname(os.path.abspath(__file__))
    dataset_dir = os.path.join(base_dir, "spider")

    # Tải và giải nén Spider dataset
    if not os.path.exists(os.path.join(dataset_dir, "train_spider.json")):
        success = download_and_extract_spider_dataset(spider_url, dataset_dir)
        if not success:
            print("Không thể tải dataset. Sử dụng dữ liệu mẫu thay thế.")
            # Tạo dữ liệu mẫu
            sample_data = [
                {
                    "question": "Tìm tên của tất cả sinh viên đã đăng ký khóa học 'Database Systems'.",
                    "db_id": "student_course",
                    "query": "SELECT students.name FROM students JOIN enrollments ON students.id = enrollments.student_id JOIN courses ON enrollments.course_id = courses.id WHERE courses.title = 'Database Systems';"
                },
                {
                    "question": "Liệt kê tất cả khóa học và số lượng sinh viên đăng ký cho mỗi khóa học.",
                    "db_id": "student_course",
                    "query": "SELECT courses.title, COUNT(enrollments.student_id) FROM courses LEFT JOIN enrollments ON courses.id = enrollments.course_id GROUP BY courses.id, courses.title;"
                },
                {
                    "question": "Tìm sinh viên có tên là 'Alice'.",
                    "db_id": "student_course",
                    "query": "SELECT * FROM students WHERE name = 'Alice';"
                }
            ]
            with open(os.path.join(dataset_dir, "train_spider.json"), "w", encoding="utf-8") as f:
                json.dump(sample_data, f, ensure_ascii=False, indent=4)
            print(f"Dữ liệu mẫu đã được lưu tại: {os.path.join(dataset_dir, 'train_spider.json')}")

    # Đường dẫn file đầu vào và đầu ra
    input_path = os.path.join(dataset_dir, "train_spider.json")
    output_path = os.path.join(dataset_dir, "processed_train.json")

    # Kiểm tra file đầu vào có tồn tại không
    if not os.path.exists(input_path):
        print(f"File đầu vào không tồn tại: {input_path}")
    else:
        preprocess_spider_data(input_path, output_path)
        print(f"Dữ liệu đã được chuẩn hóa và lưu vào: {output_path}")