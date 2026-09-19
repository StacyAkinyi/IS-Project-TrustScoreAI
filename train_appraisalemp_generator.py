import pandas as pd
from transformers import T5Tokenizer, T5ForConditionalGeneration, Trainer, TrainingArguments
import torch

# 1. Load your synthetic KPI-to-Question dataset
df = pd.read_csv("kpi_to_questions.csv")

tokenizer = T5Tokenizer.from_pretrained("t5-small")
model = T5ForConditionalGeneration.from_pretrained("t5-small")

# 2. Tokenize the inputs (KPIs) and targets (Questions)
inputs = tokenizer(df['kpi_context'].tolist(), padding=True, truncation=True, return_tensors="pt")
labels = tokenizer(df['target_question'].tolist(), padding=True, truncation=True, return_tensors="pt")

# 3. Create a Custom PyTorch Dataset
class KPIDataset(torch.utils.data.Dataset):
    def __getitem__(self, idx):
        return {"input_ids": inputs.input_ids[idx], "attention_mask": inputs.attention_mask[idx], "labels": labels.input_ids[idx]}
    def __len__(self):
        return len(df)

# 4. Fine-Tune the Model
training_args = TrainingArguments(
    output_dir="./results",
    num_train_epochs=3,
    per_device_train_batch_size=8,
    save_steps=100,
    logging_steps=10
)

trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=KPIDataset(),
)

print("Training NLP Question Generator...")
trainer.train()

# Save the custom banking model
model.save_pretrained("./trustscore_question_model")
tokenizer.save_pretrained("./trustscore_question_model")
print("Model saved successfully!")