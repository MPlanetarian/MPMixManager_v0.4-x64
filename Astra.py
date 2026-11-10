import os
import openai

def main():
    # Set your OpenAI API key here or export it as an environment variable 'OPENAI_API_KEY'
    openai.api_key = os.getenv("OPENAI_API_KEY")  
    if not openai.api_key:
        print("Error: Please set your OPENAI_API_KEY environment variable.")
        return

    model = "gpt-6-astra"  # Change to your preferred model, e.g., 'gpt-5.6-sol'

    print(f"Starting interactive chat with model '{model}'. Type 'exit' to quit.\n")

    conversation = []

    while True:
        prompt = input("You: ")
        if prompt.lower() in ("exit", "quit"):
            print("Exiting chat.")
            break

        conversation.append({"role": "user", "content": prompt})

        try:
            response = openai.chat.completions.create(
                model=model,
                messages=conversation,
                max_completion_tokens=1000
            )
            reply = response.choices[0].message.content
            print(f"AI: {reply}\n")

            conversation.append({"role": "assistant", "content": reply})

        except openai.error.OpenAIError as e:
            print(f"API error: {e}")
            break

if __name__ == "__main__":
    main()

