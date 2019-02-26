import time
import requests

BASE_URL="http://app:80"

def test_against_docker():
    with open('/test/mock_input.json', 'rb') as f:
        files = {'input': ('input', f.read(), 'application/json')}        
    resp = requests.post(f"{BASE_URL}/dss", files=files)            

    model_response = resp.json()
    assert 'id' in model_response

    exec_id = model_response['id']
    

    complete = False
    while not complete:
        status = requests.get(f"{BASE_URL}/status/{exec_id}").json()['status']
        if status == "COMPLETED":
            complete = True
        else:            

    
    resp = requests.get(f"{BASE_URL}/status/{exec_id}").json()                
    assert 'score' in resp['result']