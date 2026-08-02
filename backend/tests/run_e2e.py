import requests
import json
import sys
import time

def test_chat(prompt, capabilities):
    url = "http://127.0.0.1:8000/api/chat"
    payload = {
        "prompt": prompt,
        "capabilities": capabilities,
        "conversation_id": "test_conv_123"
    }
    
    print(f"Testing chat endpoint with capabilities: {capabilities}...")
    start_time = time.time()
    try:
        response = requests.post(url, json=payload, stream=True)
        if response.status_code != 200:
            print(f"Error: Status code {response.status_code}")
            print(response.text)
            sys.exit(1)
            
        print("Response received:")
        for line in response.iter_lines():
            if line:
                print(line.decode('utf-8'))
        
        end_time = time.time()
        print(f"\nChat stream finished successfully in {end_time - start_time:.2f} seconds!")
        
    except Exception as e:
        print(f"Connection failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    prompt = "Hello Mimir! What is 2 + 2?"
    capabilities = ["reasoning"]
    
    if len(sys.argv) > 1:
        prompt = sys.argv[1]
    if len(sys.argv) > 2:
        capabilities = sys.argv[2].split(",")
        
    test_chat(prompt, capabilities)
