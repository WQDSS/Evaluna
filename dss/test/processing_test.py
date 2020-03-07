from io import BytesIO, StringIO
import itertools
import os
import shutil
import zipfile

from unittest.mock import patch, MagicMock, Mock
import pytest
from pytest import approx
from asynctest import CoroutineMock


import wqdss
import wqdss.processing
import wqdss.tasks
import wqdss.model_execution

params = {
    'model_analysis': {
        'parameters': [
            {'name': 'NO3', 'target': '3.7', 'weight': '4', 'score_step': '0.1'},
            {'name': 'NH4', 'target': '2.4', 'weight': '2', 'score_step': '0.2'},
            {'name': 'DO', 'target': '8.0', 'weight': '2', 'score_step': '0.5'},
        ],
        "output_file": "tsr_2_seg7.csv",
    },
    'model_run': {
        'type': 'flow',
        'input_files': [
            {'name': 'hangq01.csv', 'col_name': 'Q',
                'min_val': '1', 'max_val': '2', 'steps': ['0.5']},
            {'name': 'qin_br8.csv', 'col_name': 'QWD',
                'min_val': '30', 'max_val': '40', 'steps': ['2']}
        ]
    },
}


@pytest.mark.asyncio
async def test_execute_dss():
    exec_id = 'foo'

    async def execute_on_worker_side_effect(model_name, param_values_dict, output_file):

        param_values = wqdss.model_execution.ModelExecutionPermutation.from_dict(param_values_dict)

        out_zip_io = BytesIO()
        with zipfile.ZipFile(out_zip_io, 'w') as out_zip:
            for f in param_values.files:
                out_zip.writestr(f, b'')

            data = StringIO()
            data.write('NO3,NH4,DO,\n')
            no3_val = 3.0 + (0.1 * param_values.values['hangq01.csv'])
            do_val = 4.8 + (0.02 * param_values.values['qin_br8.csv'])
            data.write(f'{no3_val},2.1,{do_val},\n')

            out_zip.writestr(output_file, data.getvalue().encode())

        return out_zip_io.getvalue()

    with patch('wqdss.processing.execute_on_worker', new=CoroutineMock(side_effect=execute_on_worker_side_effect)) as execute_on_worker:
        await wqdss.processing.execute_dss(exec_id, params)

    assert execute_on_worker.call_count == 6 * 3  # 6 values for q_in, 3 values for hangq01
    assert wqdss.processing.get_result(exec_id)[0]['score'] == approx(4.4)


def test_get_run_score():
    # test where all values are at their targets
    with patch('wqdss.processing.get_run_parameter_value', side_effect=[3.7, 2.4, 8.0]):
        result = wqdss.processing.get_run_score(params, "")
        assert result == 0

    # test where one value exceeds target (wrong direction)
    with patch('wqdss.processing.get_run_parameter_value', side_effect=[3.7, 2.4, 7.0]):
        result = wqdss.processing.get_run_score(params, "")
        assert result == approx(1.0)  # (|(7.0 - 8.0)/0.5)| / 2.0)

    # test where two values exceed target (wrong direction)
    with patch('wqdss.processing.get_run_parameter_value', side_effect=[3.8, 2.4, 7.0]):
        result = wqdss.processing.get_run_score(params, "")
        # (|(3.7 - 3.8)/0.1|) / 4.0) + (|(7.0 - 8.0)/0.5)| / 2.0)
        assert result == approx(1.25)

    # test where two values exceed target (one in wrong direction, one in right direction)
    with patch('wqdss.processing.get_run_parameter_value', side_effect=[3.6, 2.4, 7.0]):
        result = wqdss.processing.get_run_score(params, "")
        # (|(3.7 - 3.6)/0.1|) / 4.0) + (|(7.0 - 8.0)/0.5)| / 2.0)
        assert result == approx(1.25)

    # test where two values exceed target (both in right direction)
    with patch('wqdss.processing.get_run_parameter_value', side_effect=[3.6, 2.4, 9.0]):
        result = wqdss.processing.get_run_score(params, "")
        # (|(3.7 - 3.6)/0.1|) / 4.0) + (|(9.0 - 8.0)/0.5)| / 2.0)
        assert result == approx(1.25)


def test_generate_permutations():
    result = wqdss.processing.generate_permutations(params)
    value_perms = list(itertools.product([1.0, 1.5, 2.0], [
                       30.0, 32.0, 34.0, 36.0, 38.0, 40.0]))
    names = [i['name'] for i in params['model_run']['input_files']]
    expected = [dict(zip(names, v)) for v in value_perms]
    assert [r.values for r in result] == expected


@pytest.mark.asyncio
async def test_mock_stream():
    exec_id = 'mock_stream_exec'
    mock_stream_dir = "/test/mock_stream_A"
    test_params = {
        "model_run": {
            "model_name": "default_t2",
            "type": "flow",
            "input_files": [
                {"name": "hangq01.csv", "col_name": "Q",
                    "min_val": "1", "max_val": "2", "steps": ["0.5"]},
                {"name": "qin_br8.csv", "col_name": "QWD",
                    "min_val": "30", "max_val": "34", "steps": ["2"]}
            ]
        },
        "model_analysis": {
            "type": "quality",
            "output_file": "tsr_2_seg7.csv",
            "parameters": [
                {"name": "TN", "target": "0.6", "weight": "4", "score_step": "0.1"},
                {"name": "DO", "target": "11", "weight": "2", "score_step": "0.5"}
            ]
        }
    }
    shutil.copy(os.path.join(wqdss.model_registry.BASE_MODEL_DIR,
                             wqdss.model_execution.MODEL_EXE), mock_stream_dir)
    shutil.make_archive('default_t2', 'zip', mock_stream_dir)
    registry_client = wqdss.model_registry.ModelRegistryClient()
    with open("default_t2.zip", "rb") as f:
        registry_client.add_model("default_t2", f.read())

    await wqdss.processing.execute_dss(exec_id, test_params)
    dss_result = wqdss.processing.get_result(exec_id)[0]
    assert dss_result['params'].values['hangq01.csv'] == 1.0
    assert dss_result['params'].values['qin_br8.csv'] == 30.0
    assert dss_result['score'] == approx(0.8565)


# @pytest.mark.asyncio
# async def test_model_or_dir_dont_exist():

#     test_params = dict(params)
#     test_params['model_run']['model_name'] = 'somemodel'

#     with pytest.raises(model_registry.ModelNotFoundError) as excinfo:
#         await wqdss.processing.execute_dss('no-such-model', test_params)
#     assert excinfo.value.model_name == 'somemodel'

#     model_registry.MODELS['somemodel'] = '/test/does-not-exist'
#     with pytest.raises(model_registry.ModelNotFoundError) as excinfo:
#         await wqdss.processing.execute_dss('this-will-fail', test_params)

#     assert excinfo.value.model_name == 'somemodel'


def test_create_run_zip():

    test_params = dict(params)
    run_dir = '/foo/bar'

    # The ZipFile object is used as a context manager, so mock the __enter__ call
    context_mock = Mock()
    zipfile_obj = MagicMock(__enter__=Mock(return_value=context_mock))
    input_files = test_params['model_run']['input_files']
    with patch('zipfile.ZipFile', return_value=zipfile_obj) as zf:
        zipbytes = wqdss.model_execution.create_run_zip(run_dir, [f["name"] for f in input_files] + ['foobar'])
        assert zf.call_args_list[0][0][0].getvalue() is zipbytes
        assert context_mock.write.call_count == len(input_files) + 1  # One additional write for output file


@pytest.mark.asyncio
async def test_failed_processing():
    """
    Test handling of processing failure
    """

    exec_id = 'mock_stream_exec'
    mock_stream_dir = "/test/mock_stream_A"
    test_params = {
        "model_run": {
            "model_name": "default_t2",
            "type": "flow",
            "input_files": [
                {"name": "hangq07.csv", "col_name": "Q",
                    "min_val": "1", "max_val": "2", "steps": ["0.5"]},
                {"name": "qin_br8.csv", "col_name": "QWD",
                    "min_val": "30", "max_val": "34", "steps": ["2"]}
            ]
        },
        "model_analysis": {
            "type": "quality",
            "output_file": "tsr_2_seg7.csv",
            "parameters": [
                {"name": "TN", "target": "0.6", "weight": "4", "score_step": "0.1"},
                {"name": "DO", "target": "11", "weight": "2", "score_step": "0.5"}
            ]
        }
    }
    shutil.copy(os.path.join(wqdss.model_registry.BASE_MODEL_DIR,
                             wqdss.model_execution.MODEL_EXE), mock_stream_dir)
    shutil.make_archive('default_t2', 'zip', mock_stream_dir)
    registry_client = wqdss.model_registry.ModelRegistryClient()
    with open("default_t2.zip", "rb") as f:
        registry_client.add_model("default_t2", f.read())

    with pytest.raises(Exception):
        await wqdss.processing.execute_dss(exec_id, test_params)

    dss_result = wqdss.processing.get_result(exec_id)[0]
    assert dss_result['error'] is not None
    assert dss_result['score'] == 0


@pytest.mark.skip
def test_celery_task():
    assert False


@pytest.mark.skip
def test_model_execution_sync():
    assert False


@pytest.mark.skip
def test_model_execution_async():
    assert False
