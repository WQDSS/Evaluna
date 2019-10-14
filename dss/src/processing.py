import asyncio
import csv
from enum import Enum
import itertools
import logging
import os
import shutil
import uuid

import model_execution

EXECUTIONS = {}


BEST_RUNS_DIR = os.environ.get("WQDSS_BEST_RUNS_DIR", "/best_runs")

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)


def sliced(seq, n):
    return itertools.takewhile(bool, (seq[i: i + n] for i in itertools.count(0, n)))


class ExectuionState(Enum):
    RUNNING = 'RUNNING'
    COMPLETED = 'COMPLETED'


class Execution:
    def __init__(self, exec_id, model_name, state=ExectuionState.RUNNING):
        self.state = state
        self.result = None
        self.exec_id = exec_id
        self.runs = []
        self.model_execution_client = model_execution.RemoteModelExecution(model_name)
        EXECUTIONS[exec_id] = self

    def add_run(self, run_id, p):
        self.runs.append((run_id, p))

    def set_run_output(self, run_id, output):
        run = next(filter(lambda r: r[0] == run_id, self.runs))
        run_index = self.runs.index(run)
        self.runs[run_index] = tuple(list(run) + [output])

    def clean(self):
        for (run_dir, _) in self.runs:
            shutil.rmtree(run_dir)

    def mark_complete(self):
        self.state = ExectuionState.COMPLETED

    def save_best_run(self, run_id):
        best_run_out_dir = os.path.join(BEST_RUNS_DIR, self.exec_id)
        os.makedirs(best_run_out_dir, exist_ok=True)
        best_run_zip_path = os.path.join(best_run_out_dir, 'best_run.zip')

        with open(best_run_zip_path, "wb") as best_run_file:
            best_run_file.write(self.model_execution_client.get_run_zip(run_id).getvalue())

    async def execute(self, params):
        permutations = generate_permutations(params)
        num_parallel_execs = int(os.getenv("NUM_PARALLEL_EXECS", "4"))
        try:
            model_name = params['model_run']['model_name']
            logger.info(f'going to use model {model_name}')
        except:
            logger.info(f'No model name specified, or model not registered')

        for i, s in enumerate(sliced(permutations, num_parallel_execs)):
            logger.info(f'About to process slice {i}: {s}')
            awaitables = [self.execute_run_async(params, p) for p in s]
            logger.info(f'Going to call gather')
            await asyncio.gather(*awaitables)
            logger.info(f'finished slice {i}: {s}')

        run_scores = [(run_id, p.values, get_run_score(run_id, params, outfile_contents))
                      for (run_id, p, outfile_contents) in self.runs]
        best_run = min(run_scores, key=lambda x: x[2])

        # create a zip file with all of the relevant run files (inputs and outputs used for analysis)
        self.save_best_run(best_run[0])
        self.result = {'best_run': best_run[0], 'params': best_run[1], 'score': best_run[2]}

    async def execute_run_async(self, params, run_permutation):
        run_id = get_run_id()
        self.add_run(run_id, run_permutation)
        logger.info(f"going to await run {run_id}")
        out_file_contents = await self.model_execution_client.run(
            self.exec_id, run_id, run_permutation, params['model_analysis']['output_file'])
        logger.info(f"done awaiting run {run_id}")
        self.set_run_output(run_id, out_file_contents)


class ModelExecutionPermutation:

    def __init__(self, input_files, columns, values):
        self.files = input_files
        self.columns = dict(zip(self.files, columns))
        self.values = dict(zip(self.files, values))


def generate_permutations(params):
    '''
    Iterates over the input files, and the defined range of values for qwd in each of these files.
    Returns the set of all relevant permutation values for the input files
    '''
    inputs = params['model_run']['input_files']
    ranges = {i['name']: values_range(float(i['min_val']), float(
        i['max_val']), float(i['steps'])) for i in inputs}

    # for now, get a full cartesian product of the parameter values
    run_values = itertools.product(*ranges.values())
    input_file_names = ranges.keys()
    input_file_columns = [i['col_name'] for i in inputs]

    # each value in run_values includes the value to be used for each input
    # file. Now, create a dict that will hold all the necessary information:
    # input_file: (column_name, value)
    permutations = []
    for r in run_values:
        permutations.append(ModelExecutionPermutation(
            input_file_names, input_file_columns, r))

    return permutations


def values_range(min_val, max_val, step):
    '''
    Yields all values in the range [min_val, max_val] with a given step
    '''
    cur_val = min_val
    i = 0
    while cur_val < max_val:
        cur_val = min_val + (i * step)
        yield cur_val
        i = i + 1


def get_run_parameter_value(param_name, contents):
    """
    Parses outfile contents and extracts the value for the field named as `param_name` from the last row
    """

    # read the header + the last line, and strip whitespace from field names
    header = ','.join([c.lstrip() for c in contents[0].split(',')]) + '\n'
    reader = csv.DictReader([header, contents[-1]])
    return float(next(reader)[param_name])


def calc_param_score(value, target, score_step, weight):

    distance = abs(target - value)
    return (distance/score_step)/weight


def get_run_score(run_dir, params, outfile_contents):
    """
    Based on the params field 'model_analysis' find the run for this score
    """
    model_analysis_params = params['model_analysis']['parameters']
    param_scores = {}
    for param in model_analysis_params:
        param_value = get_run_parameter_value(param['name'], outfile_contents)
        param_scores[param['name']] = calc_param_score(param_value, float(
            param['target']), float(param['score_step']), float(param['weight']))

    return sum(param_scores.values())


def get_exec_id():
    return str(uuid.uuid4())


def get_run_id():
    return str(uuid.uuid4())


def get_status(exec_id):
    return EXECUTIONS[exec_id].state.value


def get_result(exec_id):
    return EXECUTIONS[exec_id].result


def get_best_run(exec_id):
    """ Returns a zip file containing the outputs of the best run for the execution. """
    best_run_out_dir = os.path.join(BEST_RUNS_DIR, exec_id, 'best_run.zip')
    return open(best_run_out_dir, 'rb').read()


async def execute_dss(exec_id, params):
    # TODO: extract handling the Execution to a context
    model_run_params = params['model_run']
    model_name = model_run_params['model_name'] if 'model_name' in model_run_params else model_execution.DEFAULT_MODEL
    current_execution = Execution(exec_id, model_name)
    try:
        await current_execution.execute(params)
    finally:
        current_execution.mark_complete()
