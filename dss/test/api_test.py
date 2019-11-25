import asyncio
import logging
import io
import json
import pathlib
import shutil
import unittest.mock as mock
import zipfile

import pytest
from asynctest import CoroutineMock

import api as service
import wq2dss.processing
import wq2dss.model_registry
import model_registry_api

logging.basicConfig(level=logging.DEBUG)

INPUT_EXAMPLE = """
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
            { "name":"NO3", "target":"3.7", "weight":"4", "score_step":"0.1" },
            { "name":"NH4", "target":"2.4", "weight":"2", "score_step":"0.2" },
            { "name":"DO", "target":"8", "weight":"2", "score_step":"0.5" }
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
    RESPONSE = {"score": 4.2, "params": mock.Mock(values=[])}

    file_obj = tmp_path / "data.t"
    file_obj.write_bytes(INPUT_EXAMPLE.encode())

    files = {'input': (file_obj.name, file_obj.read_bytes(), 'application/json')}
    data = {'model_name': 'some_model'}

    start_event = asyncio.Event()
    wq2dss.processing.EXECUTIONS = {}

    async def my_execute(params):
        await start_event.wait()
        expected_params = json.loads(INPUT_EXAMPLE)
        expected_params['model_run']['model_name'] = 'some_model'
        assert params == expected_params
        wq2dss.processing.EXECUTIONS[next(iter(wq2dss.processing.EXECUTIONS.keys()))].result = RESPONSE
        return RESPONSE

    with api.requests:
        with mock.patch.object(wq2dss.processing.Execution, 'execute', new=CoroutineMock(side_effect=my_execute)):
            resp = api.requests.post("/dss", data=data, files=files)

    model_response = resp.json()
    assert 'id' in model_response
    exec_id = model_response['id']

    # we check for the running state before allowing the model to complete
    assert api.requests.get(f"/status/{exec_id}").json()['status'] == wq2dss.processing.ExectuionState.RUNNING.value

    # the model can now execute
    start_event.set()

    resp = api.requests.get(f"/status/{exec_id}").json()
    assert resp['status'] == wq2dss.processing.ExectuionState.COMPLETED.value
    assert resp['result']['score'] == RESPONSE['score']

    # check that the best run output is reachable
    s = io.BytesIO()
    with zipfile.ZipFile(s, 'w'):
        pass

    empty_zip_contents = s.getvalue()
    with mock.patch('wq2dss.processing.get_best_run', return_value=empty_zip_contents):
        resp = api.requests.get(f"/best_run/{exec_id}")
        assert resp.status_code == 200
        assert resp.content == empty_zip_contents
        assert resp.headers['content-type'] == 'application/zip'


def test_get_best_run_not_found(api):
    s = io.BytesIO()
    with zipfile.ZipFile(s, 'w'):
        pass

    empty_zip_contents = s.getvalue()
    with mock.patch('wq2dss.processing.get_best_run', return_value=empty_zip_contents):
        resp = api.requests.get(f"/best_run/foobar")
        assert resp.status_code == 400
        assert resp.json() == {"exec_id": "foobar"}


def test_get_best_run_in_progress(api):
    s = io.BytesIO()
    with zipfile.ZipFile(s, 'w'):
        pass

    empty_zip_contents = s.getvalue()
    with mock.patch('wq2dss.processing.get_best_run', return_value=empty_zip_contents):
        with mock.patch('wq2dss.processing.get_status', return_value='IN_PROGRESS'):
            resp = api.requests.get(f"/best_run/foobar")
            assert resp.status_code == 400
            assert resp.json() == {"exec_id": "foobar"}


def test_add_model(tmp_path):
    file_a = tmp_path / "file.a"
    file_a.write_bytes("this is a file".encode())

    file_b = tmp_path / "file.b"
    file_b.write_bytes("this is b file".encode())

    model_zip = tmp_path / "model.zip"

    with zipfile.ZipFile(model_zip, 'w') as z:
        z.write(file_a)
        z.write(file_b)

    files = {'model': ('test_model', model_zip.read_bytes(), 'application/zip')}
    resp = model_registry_api.api.requests.post("/models", files=files)

    model_added_resp = resp.json()
    assert 'model_name' in model_added_resp
    assert model_added_resp['model_name'] == 'test_model'
    list_models_resp = model_registry_api.api.requests.get('/models')
    models_list = list_models_resp.json()
    assert 'test_model' in models_list['models']


def test_model_registry_client(tmp_path_factory):

    tmp_path = tmp_path_factory.mktemp("new_model_dir")
    tmp_model_base = tmp_path_factory.mktemp("model_base")
    with mock.patch.object(wq2dss.model_registry, 'BASE_MODEL_DIR', tmp_model_base):
        # add a test model
        file_a = tmp_path / "file.a"
        file_a.write_bytes("this is a file".encode())
        model_zip = tmp_path / "model.zip"

        with zipfile.ZipFile(model_zip, 'w') as z:
            z.write(file_a)

        files = {'model': ('test_model-new', model_zip.read_bytes(), 'application/zip')}
        model_registry_api.api.requests.post("/models", files=files)

        # fetch the test model
        model_registry_client = wq2dss.model_registry.ModelRegistryClient("/models", model_registry_api.api.requests)
        model_contents = model_registry_client.get_model_by_name("test_model-new")
        returned_model = zipfile.ZipFile(io.BytesIO(model_contents))
        assert returned_model.namelist() == ["file.a"]


def test_model_registry_client_model_in_dir(tmp_path):

    # add a test model
    model_dir = tmp_path / "test_model-dir" / "subdir"
    model_dir.mkdir(parents=True)
    file_a = model_dir / "file.a"
    file_a.write_bytes("this is a file".encode())
    file_b = model_dir / "file.b"
    file_b.write_bytes("this is another file".encode())
    model_zip = tmp_path / "model.zip"

    with zipfile.ZipFile(model_zip, 'w') as z:
        z.write(file_a, arcname=pathlib.PurePath(*file_a.parts[-2:]))
        z.write(file_b, arcname=pathlib.PurePath(*file_b.parts[-2:]))

    try:
        shutil.rmtree(wq2dss.model_registry.BASE_MODEL_DIR)
    except FileNotFoundError:
        pass
    files = {'model': ('test_model-new-in-dir', model_zip.read_bytes(), 'application/zip')}
    model_registry_api.api.requests.post("/models", files=files)

    # fetch the test model
    model_registry_client = wq2dss.model_registry.ModelRegistryClient("/models", model_registry_api.api.requests)
    model_contents = model_registry_client.get_model_by_name("test_model-new-in-dir")

    returned_model = zipfile.ZipFile(io.BytesIO(model_contents))
    assert sorted(returned_model.namelist()) == ['file.a', 'file.b']
