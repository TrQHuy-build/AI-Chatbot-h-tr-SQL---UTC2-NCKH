import os
import json
from unsloth import FastLanguageModel
from transformers import TrainingArguments, Trainer
from datasets import Dataset

def load_training_data(data_path):
    """
    Tải dữ liệu huấn luyện từ file JSON.
    """
    with open(data_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def prepare_dataset_for_training(training_data):
    """
    Chuẩn bị dataset cho quá trình huấn luyện.
    """
    def formatting_func(examples):
        texts = []
        for instruction, input_text, output in zip(examples["instruction"], examples["input"], examples["output"]):
            text = f"Instruction: {instruction}\nInput: {input_text}\nOutput: {output}"
            texts.append(text)
        return {"text": texts}

    # Chuyển đổi dữ liệu thành định dạng phù hợp
    dataset_data = {
        "instruction": [item.get("instruction", "") for item in training_data],
        "input": [item.get("input", "") for item in training_data],
        "output": [item.get("output", "") for item in training_data]
    }
    dataset = Dataset.from_dict(dataset_data)
    dataset = dataset.map(formatting_func, batched=True)
    return dataset

def fine_tune_phi3_model(data_path, output_dir):
    """
    Fine-tune mô hình Phi-3 bằng Unsloth.
    """
    # Tải dữ liệu huấn luyện
    print("Đang tải dữ liệu huấn luyện...")
    training_data = load_training_data(data_path)
    dataset = prepare_dataset_for_training(training_data)

    # Tải mô hình Phi-3
    print("Đang tải mô hình Phi-3...")
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name="microsoft/phi-2",
        max_seq_length=2048,
        load_in_4bit=True,
        device_map="auto"
    )

    # Cấu hình huấn luyện
    training_args = TrainingArguments(
        output_dir=output_dir,
        overwrite_output_dir=True,
        num_train_epochs=2,
        per_device_train_batch_size=4,
        save_steps=100,
        save_total_limit=2,
        logging_dir=os.path.join(output_dir, "logs"),
        logging_steps=50,
        learning_rate=5e-5,
        warmup_steps=50,
        weight_decay=0.01,
        fp16=True if torch.cuda.is_available() else False,
    )

    # Huấn luyện mô hình
    print("Bắt đầu quá trình fine-tuning...")
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=dataset,
        tokenizer=tokenizer
    )
    trainer.train()

    # Lưu mô hình đã fine-tune
    print("Lưu mô hình đã fine-tune...")
    model.save_pretrained(output_dir)
    tokenizer.save_pretrained(output_dir)
    print(f"Mô hình đã được lưu tại: {output_dir}")

if __name__ == "__main__":
    import torch
    
    # Đường dẫn dữ liệu huấn luyện và thư mục lưu mô hình
    data_path = "./datasets/spider/processed_train.json"
    output_dir = "./model_weights"

    # Kiểm tra dữ liệu huấn luyện
    if not os.path.exists(data_path):
        print(f"Dữ liệu huấn luyện không tồn tại: {data_path}")
        print("Vui lòng chạy data_preprocessing.py trước.")
    else:
        os.makedirs(output_dir, exist_ok=True)
        fine_tune_phi3_model(data_path, output_dir)