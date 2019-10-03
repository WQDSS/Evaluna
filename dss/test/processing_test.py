import itertools
import os
import shutil

from unittest.mock import patch
import pytest
from pytest import approx
from asynctest import CoroutineMock

import processing

params = {
    'model_analysis' : {
        'parameters' : [
            {'name': 'NO3', 'target':'3.7', 'weight':'4', 'score_step':'0.1' },
            {'name': 'NH4', 'target':'2.4', 'weight':'2', 'score_step':'0.2' },
            {'name': 'DO', 'target':'8.0', 'weight':'2', 'score_step':'0.5'},
        ],
        "output_file": "tsr_2_seg7.csv",
    },
    'model_run': {
        'type': 'flow',
        'input_files': [
            {'name': 'hangq01.csv', 'col_name': 'Q', 'min_val': '1', 'max_val':'2', 'steps':'0.5' },
            {'name': 'qin_br8.csv', 'col_name': 'QWD', 'min_val': '30', 'max_val':'40', 'steps':'2' }
        ]
    },       
}

@pytest.mark.asyncio
async def test_execute_dss():    
    exec_id = 'foo'

    def get_run_dir():
        i = 1
        while True:
            yield f'run_dir_{i}'
            i = i+1
    
    run_dirs = get_run_dir()
    def create_out_csv(exec_id, params, param_values):
        '''
        Create a dummy csv file for tests
        '''
        run_dir = next(run_dirs)        
        try:        
            os.makedirs(run_dir)
        except:
            pass

        with open(os.path.join(run_dir, params['model_analysis']['output_file']), 'w') as f:
            f.write('NO3,NH4,DO,\n')
            no3_val = 3.0 + (0.1 * param_values['hangq01.csv'])
            do_val = 4.8 + (0.02 * param_values['qin_br8.csv'])
            f.write(f'{no3_val},2.1,{do_val},\n')
        
        return run_dir

    with patch('processing.exec_model_async', new=CoroutineMock()) as exec_model:
        with patch('processing.prepare_run_dir') as prepare_run_dir:            
            prepare_run_dir.side_effect = create_out_csv
            await processing.execute_dss(exec_id, params)            
        
    assert exec_model.call_count == 6 * 3  #  6 values for q_in, 3 values for hangq01
    assert prepare_run_dir.call_count == 6 * 3
    assert processing.get_result('foo')['score'] == approx(2.175)    



def test_get_run_score():
    RUN_DIR='foo'
    with patch('processing.get_out_file_contents'):
        # test where all values are at their targets
        with patch('processing.get_run_parameter_value', side_effect=[3.7, 2.4, 8.0]):
            result = processing.get_run_score(RUN_DIR, params)
            assert result == 0

        # test where one value exceeds target (wrong direction)
        with patch('processing.get_run_parameter_value', side_effect=[3.7, 2.4, 7.0]):
            result = processing.get_run_score(RUN_DIR, params)
            assert result == approx(1.0)  #  (|(7.0 - 8.0)/0.5)| / 2.0)

        # test where two values exceed target (wrong direction)
        with patch('processing.get_run_parameter_value', side_effect=[3.8, 2.4, 7.0]):
            result = processing.get_run_score(RUN_DIR, params)
            assert result == approx(1.25)  #  (|(3.7 - 3.8)/0.1|) / 4.0) + (|(7.0 - 8.0)/0.5)| / 2.0)

        # test where two values exceed target (one in wrong direction, one in right direction)
        with patch('processing.get_run_parameter_value', side_effect=[3.6, 2.4, 7.0]):
            result = processing.get_run_score(RUN_DIR, params)
            assert result == approx(1.25)  #  (|(3.7 - 3.6)/0.1|) / 4.0) + (|(7.0 - 8.0)/0.5)| / 2.0)

        # test where two values exceed target (both in right direction)
        with patch('processing.get_run_parameter_value', side_effect=[3.6, 2.4, 9.0]):
            result = processing.get_run_score(RUN_DIR, params)
            assert result == approx(1.25)  #  (|(3.7 - 3.6)/0.1|) / 4.0) + (|(9.0 - 8.0)/0.5)| / 2.0)

def test_generate_permutations():
    result = processing.generate_permutations(params)
    value_perms = list(itertools.product([1.0, 1.5, 2.0], [30.0, 32.0, 34.0, 36.0, 38.0, 40.0]))
    names = [i['name'] for i in params['model_run']['input_files']]
    expected = [dict(zip(names, v)) for v in value_perms]
    assert result == expected

@pytest.mark.asyncio
async def test_mock_stream():
    exec_id = 'mock_stream_exec'
    mock_stream_dir = "/test/mock_stream_A"
    test_params = {
        "model_run": {
            "type": "flow",
            "input_files": [
                {"name": "hangq01.csv", "col_name": "Q", "min_val": "1", "max_val": "2", "steps": "0.5"},
                {"name": "qin_br8.csv", "col_name": "QWD", "min_val": "30", "max_val": "34", "steps": "2"}
            ]
        },
        "model_analysis": {
            "type": "quality",
            "output_file": "tsr_2_seg7.csv",
            "parameters": [
                {"name": "TN", "target": "0.6", "weight": "4", "score_step": "0.1" },
                {"name": "DO", "target": "11", "weight": "2", "score_step": "0.5" }
            ]
        }
    }
    shutil.copy(os.path.join(processing.BASE_MODEL_DIR,
                             processing.MODEL_EXE), mock_stream_dir)
    processing.MODELS["default"] = mock_stream_dir
    await processing.execute_dss(exec_id, test_params)
    dss_result = processing.get_result(exec_id)
    assert dss_result['params']['hangq01.csv'] == 1.0
    assert dss_result['params']['qin_br8.csv'] == 30.0
    assert dss_result['score'] == approx(-1.336)

@pytest.mark.asyncio
async def test_model_or_dir_dont_exist():
    
    test_params = dict(params)
    test_params['model_run']['model_name'] = 'somemodel'    

    with pytest.raises(processing.ModelNotFoundError) as excinfo:
        await processing.execute_dss('no-such-model', test_params)
    assert excinfo.value.model_name == 'somemodel'
    
    
    processing.MODELS['somemodel'] = '/test/does-not-exist'
    with pytest.raises(processing.ModelDirNotFoundError) as excinfo:
        await processing.execute_dss('this-will-fail', test_params)

    assert excinfo.value.model_dir == '/test/does-not-exist'
