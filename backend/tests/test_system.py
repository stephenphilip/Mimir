import requests
import json
import time
import sys

URL = "http://127.0.0.1:8000/api/chat"
CONV_ID = "full_system_test_conv"

TEST_CASES = [
    {
        "prompt": "Hello Mimir! My name is Alice and I am a software engineer.",
        "capabilities": ["reasoning"],
        "desc": "1. Greeting & Memory Injection"
    },
    {
        "prompt": "What is my name and my profession?",
        "capabilities": ["reasoning"],
        "desc": "2. Memory Retrieval"
    },
    {
        "prompt": "Write a python script that calculates the first 10 prime numbers and prints them.",
        "capabilities": ["reasoning", "python_execution"],
        "desc": "3. Code Generation & Execution"
    },
    {
        "prompt": "Create an excel file named 'budget.xlsx' with some dummy monthly budget data (Rent 1000, Food 300).",
        "capabilities": ["reasoning", "python_execution", "excel_generation"],
        "desc": "4. Document Creation via Tool"
    }
]

def run_test_case(case):
    print(f"\n{'='*50}")
    print(f"Executing Test: {case['desc']}")
    print(f"Prompt: {case['prompt']}")
    print(f"Capabilities: {case['capabilities']}")
    print(f"{'='*50}")

    payload = {
        "prompt": case["prompt"],
        "capabilities": case["capabilities"],
        "conversation_id": CONV_ID
    }
    
    start = time.time()
    try:
        response = requests.post(URL, json=payload, stream=True)
        if response.status_code != 200:
            print(f"HTTP ERROR: {response.status_code}\n{response.text}")
            return False

        for line in response.iter_lines():
            if line:
                line_str = line.decode('utf-8')
                if line_str.startswith("data: "):
                    data = json.loads(line_str[6:])
                    if data["type"] == "status":
                        print(f"[STATUS] {data['status']}")
                    elif data["type"] == "content":
                        print(data["text"], end="", flush=True)
                    elif data["type"] == "execution_result":
                        print(f"\n[TOOL EXECUTION]")
                        print(f"Success: {data['success']}")
                        print(f"Stdout: {data['stdout'].strip()}")
                        print(f"Stderr: {data['stderr'].strip()}")
                        print(f"Artifacts: {data['artifacts']}")
                    elif data["type"] == "error":
                        print(f"\n[ERROR] {data['message']}")
                    elif data["type"] == "done":
                        print("\n[DONE]")
    except Exception as e:
        print(f"\nRequest failed: {e}")
        return False
        
    duration = time.time() - start
    print(f"\nTime taken: {duration:.2f} seconds")
    return True

if __name__ == "__main__":
    print("Starting full system test...")
    for case in TEST_CASES:
        success = run_test_case(case)
        if not success:
            print("Test failed. Aborting suite.")
            sys.exit(1)
        time.sleep(2) # brief pause between turns
    print("\nAll tests completed.")
