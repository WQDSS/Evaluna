import asyncio
import logging
import json
import threading
import unittest.mock as mock
import zipfile

import pytest
from asynctest import CoroutineMock

import api as service
import processing


logging.basicConfig(level=logging.DEBUG)

INPUT_EXAMPLE="""
{
    "model_run": {
        "type": "flow",
        "input_files": [
            { "name":"a.csv", "min_qwd":"1000", "max_qwd":"2000", "steps":"500" },
            { "name":"b.csv", "min_qwd":"0", "max_qwd":"100", "steps":"50" }
        ]
    },
    "model_analysis": {
        "type": "quality",
        "output_file": "out.csv",
        "parameters": [
            { "name":"NO3", "target":"3.7", "weight":"4", "score_step":"0.1", "desired_direction":"-1" },
            { "name":"NH4", "target":"2.4", "weight":"2", "score_step":"0.2", "desired_direction":"-1" },
            { "name":"DO", "target":"8", "weight":"2", "score_step":"0.5", "desired_direction":"+1" }
        ]
    }
}
"""

@pytest.fixture
def api():
    return service.api

def test_execution_not_found(api):
    assert api.requests.get(f"/status/DOES_NOT_EXIST").json()['status'] == 'NOT_FOUND'

def test_dss_execution(api, tmp_path):
    '''
    Test the execution of a dss, including setting the paramters, and polling for a result
    '''    
    RESPONSE={"score" : 4.2}    

    file_obj = tmp_path / "data.t"
    file_obj.write_bytes(INPUT_EXAMPLE.encode())
    PROCESSING_DURATION = 1
    
    files = {'input': (file_obj.name, file_obj.read_bytes(), 'application/json')}
    data = {'processing_duration' : PROCESSING_DURATION}
       
    start_event = asyncio.Event()

    async def my_execute(params):        
        await start_event.wait()        
        assert params == json.loads(INPUT_EXAMPLE)
        return RESPONSE


    with api.requests:            
        with mock.patch.object(processing.Execution, 'execute', new=CoroutineMock(side_effect=my_execute)) as execute:
            resp = api.requests.post("/dss", data=data, files=files)                 
        
    model_response = resp.json()
    assert 'id' in model_response
    exec_id = model_response['id']

    # we check for the running state before allowing the model to complete
    assert api.requests.get(f"/status/{exec_id}").json()['status'] == processing.ExectuionState.RUNNING.value

    # the model can now execute
    start_event.set()    
    
    resp = api.requests.get(f"/status/{exec_id}").json()                
    assert resp['status'] == processing.ExectuionState.COMPLETED.value
    assert resp['result'] == RESPONSE


def test_add_model(api, tmp_path):
    file_a = tmp_path / "file.a"
    file_a.write_bytes("this is a file".encode())

    file_b = tmp_path / "file.b"
    file_b.write_bytes("this is b file".encode())
    
    model_zip = tmp_path / "model.zip"

    with zipfile.ZipFile(model_zip, 'w') as z:
        z.write(file_a)
        z.write(file_b)
        
    files = {'model': ('test_model', model_zip.read_bytes(), 'application/zip')}
    with mock.patch('processing.add_model') as add_model:
        resp = api.requests.post("/add-model", files=files)
    
    model_added_resp = resp.json()
    assert 'model_name' in model_added_resp
    assert model_added_resp['model_name'] == 'test_model'
    add_model.assert_called_once_with('test_model', model_zip.read_bytes())