import pandas as pd
import random

def generate_synthetic_dataset(num_records=1200):
    data = []
    
    for _ in range(num_records):
        loans = random.randint(40, 160)
        accuracy = round(random.uniform(70.0, 99.9), 1)
        errors = random.randint(0, 6)
        
        kpi_context = f"loans: {loans}, accuracy: {accuracy}%, errors: {errors}"
        
        # High Performers: Focus on skills, methods, and sharing expertise
        if loans >= 110 and accuracy >= 90.0 and errors <= 1:
            questions = (
                "1. You have consistently exceeded volume targets; what specific workflows helped you achieve this? | "
                "2. Your transaction accuracy is exceptional; how do you maintain this precision during peak hours? | "
                "3. What best practices can you share with your peers to elevate overall team performance?"
            )
            
        # Struggling Performers: Focus on effort, bottlenecks, and support needs
        elif accuracy < 85.0 or errors >= 3:
            questions = (
                "1. We noticed a recent dip in accuracy; what operational bottlenecks are you currently facing? | "
                "2. With the recent increase in errors, how is the current workload affecting your document review process? | "
                "3. What additional training, resources, or system support do you need to improve these metrics next month?"
            )
            
        # Average/Steady Performers: Focus on growth and consistency
        else:
            questions = (
                "1. You are maintaining a steady baseline; what are your primary focus areas for the upcoming month? | "
                "2. Are there any specific steps in the transaction process currently causing you friction? | "
                "3. What new skills or cross-training areas would you like to explore to increase your overall output?"
            )
            
        data.append({
            "kpi_context": kpi_context,
            "target_question": questions
        })
        
    df = pd.DataFrame(data)
    df.to_csv("kpi_to_questions.csv", index=False)
    print(f"Generated 'kpi_to_questions.csv' with 3-question targets for {num_records} records.")

if __name__ == "__main__":
    generate_synthetic_dataset()