# # from transformers import AutoTokenizer, AutoModelForCausalLM

# # model_name = "microsoft/Phi-3-mini-128k-instruct"

# # print("Loading tokenizer...")
# # tokenizer = AutoTokenizer.from_pretrained(model_name)

# # print("Loading model...")
# # model = AutoModelForCausalLM.from_pretrained(
# #     model_name,
# #     device_map="auto",
# #     trust_remote_code=True
# # )

# # prompt = "What is machine learning?"

# # messages = [
# #     {"role": "user", "content": prompt}
# # ]

# # inputs = tokenizer.apply_chat_template(
# #     messages,
# #     return_tensors="pt",
# #     add_generation_prompt=True
# # )

# # outputs = model.generate(
# #     inputs,
# #     max_new_tokens=100
# # )

# # response = tokenizer.decode(outputs[0], skip_special_tokens=True)

# # print(response)




# import requests

# response = requests.post(
#     "http://localhost:11434/api/generate",
#     json={
#         "model": "qwen2.5:3b",
#         "prompt": "Introduce yourself in one sentence.",
#         "stream": False
#     }
# )

# print(response.json()["response"])

# import speech_recognition as sr

# r = sr.Recognizer()

# with sr.Microphone() as source:
#     print("Speak...")
#     audio = r.listen(source)

# with open("test.wav", "wb") as f:
#     f.write(audio.get_wav_data())

# print("Saved test.wav")
from assistant.ai_service import get_ai_response

