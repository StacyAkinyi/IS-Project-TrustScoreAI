import pandas as pd
import random

def generate_synthetic_dataset(num_records=500):
    data = []
    
    for _ in range(num_records):
        # Generate realistic base banking metrics
        loans = random.randint(40, 160)
        accuracy = round(random.uniform(70.0, 99.9), 1)
        errors = random.randint(0, 6)
        
        # Format the input string EXACTLY as the FastAPI backend will send it
        kpi_context = f"loans: {loans}, accuracy: {accuracy}%, errors: {errors}"
        
        # Rule-based logic to determine the most appropriate contextual question
        if loans >= 120 and accuracy >= 95.0 and errors <= 1:
            question = random.choice([
                f"Your loan volume is exceptionally high at {loans} units while maintaining a stellar {accuracy}% accuracy. How are you managing this pace, and what best practices can we share with the team?",
                f"You've pushed through {loans} loans with almost zero errors. Are you experiencing any burnout at this volume, or is your current workflow fully sustainable?"
            ])
            
        elif loans >= 100 and accuracy < 85.0 and errors >= 3:
            question = random.choice([
                f"You are processing a high volume of loans ({loans}), but we've seen {errors} compliance errors recently, dropping accuracy to {accuracy}%. Is the current workload pressure causing bottlenecks in your documentation checks?",
                f"Your output velocity is great, but transaction accuracy dipped to {accuracy}%. What specific support or system adjustments do you need to help reduce these {errors} recent errors?"
            ])
            
        elif loans < 80 and accuracy >= 95.0:
            question = random.choice([
                f"Your transaction accuracy is near perfect at {accuracy}%, but your loan volume is slightly below the branch average at {loans}. Are you facing any client-side delays or system lag?",
                f"We see you are prioritizing precision with {accuracy}% accuracy and only {errors} errors. What operational hurdles are currently preventing you from scaling your loan volumes past {loans}?"
            ])
            
        elif errors >= 4:
            question = random.choice([
                f"We've flagged a spike of {errors} operational errors this cycle, bringing your accuracy to {accuracy}%. Can you walk me through the challenges you're facing with the current compliance protocols?",
                f"With {errors} recent errors recorded, how are you finding the current system workflows? Is there a specific step in the transaction process causing friction?"
            ])
            
        else:
            # Average / Steady performers
            question = random.choice([
                f"You're maintaining a steady baseline with {loans} loans and {accuracy}% accuracy. What are your primary focus areas for the upcoming month to push these metrics higher?",
                f"With a solid {accuracy}% accuracy and {errors} errors, your performance is stable. Are there any new skills or training areas you'd like to focus on to increase your overall volume?"
            ])
            
        data.append({
            "kpi_context": kpi_context,
            "target_question": question
        })
        
    df = pd.DataFrame(data)
    df.to_csv("kpi_to_questions.csv", index=False)
    print(f"Successfully generated 'kpi_to_questions.csv' with {num_records} training pairs!")

if __name__ == "__main__":
    generate_synthetic_dataset(500)