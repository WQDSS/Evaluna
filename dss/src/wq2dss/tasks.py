import asyncio
import base64
from io import BytesIO
import time

from celery.exceptions import TimeoutError

from .celery import app
from .model_execution import create_run_zip, exec_model, prepare_run_dir, ModelExecutionPermutation
from .model_registry import ModelRegistryClient


@app.task
def model_exec(model_name, param_values_as_dict, output_file):
    model_run = CeleryModelExecution(model_name)
    param_values = ModelExecutionPermutation.from_dict(param_values_as_dict)
    out_bytes = model_run.run(param_values, output_file)

    return {"result": base64.b64encode(out_bytes.getvalue()).decode('ascii')}


async def get_result(async_task_result, timeout=None, interval=0.5):

    # wait until timeout expires
    start_time = time.time()
    if timeout is None:
        def condition(): return True
    else:
        end_time = start_time + timeout

        def condition():
            return end_time >= time.time()

    while True:
        try:
            if async_task_result.ready():
                result = async_task_result.get(timeout=0.1)  # expected to return immediately
                return base64.b64decode(result["result"])
            elif condition():
                await asyncio.sleep(interval)
            else:
                raise TimeoutError('The operation timed out')
        except Exception:
            # if we're going to raise an error, make sure we `forget` the result
            try:
                async_task_result.forget()
            except NotImplementedError:
                pass
            raise


class CeleryModelExecution:
    """
    This is what gets executed on the worker side via the task
    """

    def __init__(self, model_name):
        self.model_registry_client = ModelRegistryClient()
        self.model_contents = self.model_registry_client.get_model_by_name(model_name)

    def run(self, param_values, output_file):
        run_dir = prepare_run_dir(param_values, self.model_contents)
        exec_model(run_dir)
        return BytesIO(create_run_zip(run_dir, list(param_values.files) + [output_file]))


async def execute_on_worker(model_name, param_values, output_file):
    async_result = model_exec.delay(model_name, param_values, output_file)
    return await get_result(async_result)
