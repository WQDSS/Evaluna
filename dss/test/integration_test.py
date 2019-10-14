import json
import os
import secrets
import time
import zipfile

import requests

BASE_URL = 'http://app:80'
BASE_MODEL_REGISTRY_URL = 'http://model-registry:80'
TEST_MODEL_DIR = '/test/mock_stream_A/'


def test_against_docker():

    # load custom model
    model_name = f'my-model-{secrets.randbelow(42)}'
    model_file_name = 'model_zip'
    with zipfile.ZipFile(model_file_name, 'w') as z:
        for f in os.listdir(TEST_MODEL_DIR):
            z.write(os.path.join(TEST_MODEL_DIR, f), arcname=f)

    with open(model_file_name, 'rb') as f:
        files = {'model': (model_name, f.read(), 'application/zip')}

    resp = requests.post(f'{BASE_MODEL_REGISTRY_URL}/models', files=files)
    add_model_resp = resp.json()
    assert add_model_resp['model_name'] == model_name

    # execute dss with model

    with open('/test/mock_input.json', 'rb') as f:
        mock_input = json.load(f)

    files = {'input': ('input', json.dumps(mock_input), 'application/json')}
    data = {'model_name': model_name}
    resp = requests.post(f"{BASE_URL}/dss", files=files, data=data)

    model_response = resp.json()
    assert 'id' in model_response

    exec_id = model_response['id']

    complete = False
    while not complete:
        status = requests.get(f"{BASE_URL}/status/{exec_id}").json()['status']
        if status == "COMPLETED":
            complete = True
        else:
            time.sleep(5)

    resp = requests.get(f"{BASE_URL}/status/{exec_id}").json()
    assert 'score' in resp['result']
