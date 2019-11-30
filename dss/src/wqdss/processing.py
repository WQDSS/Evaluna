import asyncio
import csv
import datetime
from enum import Enum
import itertools
import logging
import os
import shutil
import uuid

from .model_execution import get_out_contents, ModelExecutionPermutation, DEFAULT_MODEL
from .tasks import execute_on_worker

EXECUTIONS = {}


BEST_RUNS_DIR = os.environ.get("WQDSS_BEST_RUNS_DIR", os.path.join("/", "best_runs"))

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)


def sliced(seq, n):
    return itertools.takewhile(bool, (seq[i: i + n] for i in itertools.count(0, n)))


class ExectuionState(Enum):
    RUNNING = 'RUNNING'
    COMPLETED = 'COMPLETED'


class Execution:

    class Run:
        def __init__(self, run_id, permutation):
            self.run_id = run_id
            self.permutation = permutation
            self.result = None

        def get_run_output(self, output_file):
            if self.result is not None:
                return get_out_contents(self.result, output_file)
            else:
                raise Execution.RunNotCompletedError()

        def save_results(self, results_zip_file):
            with open(results_zip_file, "wb") as run_file:
                run_file.write(self.result)

        def score(self, params):
            out_file = params['model_analysis']['output_file']
            return get_run_score(params, self.get_run_output(out_file))

    class RunNotCompletedError(Exception):
        pass

    def __init__(self, exec_id, execute_func, state=ExectuionState.RUNNING):
        self.state = state
        self.result = None
        self.exec_id = exec_id
        self.runs = []
        self.execute_func = execute_func
        self.output_file = None
        EXECUTIONS[exec_id] = self
        self.model_name = None
        self.start_time = None

    def add_run(self, run_id, p):
        run = Execution.Run(run_id, p)
        self.runs.append(run)
        return run

    def find_best_run(self, params):

        def run_score(run):
            return run.score(params)

        return min(self.runs, key=run_score)

    def clean(self):
        shutil.rmtree(BEST_RUNS_DIR)

    def mark_complete(self):
        self.state = ExectuionState.COMPLETED

    def save_best_run(self, run):
        best_run_zip_path = best_run_file(self.exec_id)
        os.makedirs(os.path.dirname(best_run_zip_path), exist_ok=True)
        run.save_results(best_run_zip_path)

    async def execute(self, params):
        permutations = generate_permutations(params)
        num_parallel_execs = int(os.getenv("NUM_PARALLEL_EXECS", "-1"))
        try:
            self.model_name = params['model_run']['model_name']
        except KeyError:
            self.model_name = DEFAULT_MODEL

        self.start_time = datetime.datetime.now()
        logger.info(f'going to use model {self.model_name}')

        self.output_file = params['model_analysis']['output_file']

        try:
            if num_parallel_execs > 0 and len(permutations) > num_parallel_execs:
                for i, s in enumerate(sliced(permutations, num_parallel_execs)):
                    logger.info(f'About to process slice {i}: {s}')
                    awaitables = [self.execute_run_async(self.model_name, params, p) for p in s]
                    logger.info(f'Going to call gather')
                    await asyncio.gather(*awaitables)
                    logger.info(f'finished slice {i}: {s}')
            else:
                logger.info(f'going to execute all permutations')
                awaitables = [self.execute_run_async(self.model_name, params, p) for p in permutations]
                logger.info(f'Going to call gather')
                await asyncio.gather(*awaitables)
                logger.info('Done executing all permutations')

            best_run = self.find_best_run(params)

            # create a zip file with all of the relevant run files (inputs and outputs used for analysis)
            self.save_best_run(best_run)
            self.result = {'best_run': best_run.run_id, 'params': best_run.permutation, 'score': best_run.score(params)}
        except Exception as e:
            logger.error("An error occurred during processing")
            self.result = {'best_run': 'FAILED', 'score': 0, 'error': str(e)}
            raise

    async def execute_run_async(self, model_name, params, run_permutation):
        run_id = get_run_id()
        run = self.add_run(run_id, run_permutation)
        logger.info(f"going to await run {run_id} for model {model_name}")
        run.result = await self.execute_func(model_name, run.permutation.as_dict(), self.output_file)
        logger.info(f"done awaiting run {run_id}")


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
    permutations = [
        ModelExecutionPermutation(input_file_names, input_file_columns, r) for r in run_values]

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


def get_run_score(params, outfile_contents):
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


def best_run_file(exec_id):
    return os.path.join(BEST_RUNS_DIR, exec_id, 'best_run.zip')


def get_best_run(exec_id):
    """ Returns a zip file containing the outputs of the best run for the execution. """
    with open(best_run_file(exec_id), 'rb') as f:
        return f.read()


def simple_execution(exec_id, execution):
    simple_exec = {
        'id': exec_id,
        'model_name': execution.model_name,
        'start_time': str(execution.start_time),
        'result': dict(execution.result)
    }
    simple_exec['result']['params'] = simple_exec['result']['params'].as_dict()
    return simple_exec


def get_executions():
    return {"executions": [simple_execution(exec_id, execution) for exec_id, execution in EXECUTIONS.items()]}


async def execute_dss(exec_id, params):
    # TODO: extract handling the Execution to a context
    # model_run_params = params['model_run']
    # model_name = model_run_params['model_name'] if 'model_name' in model_run_params else DEFAULT_MODEL
    current_execution = Execution(exec_id, execute_on_worker)
    try:
        await current_execution.execute(params)
    finally:
        current_execution.mark_complete()
