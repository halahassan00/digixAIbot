import requests
response = requests.get("https://digix-ai.com/training-programs")
print(response.text[:3000])
