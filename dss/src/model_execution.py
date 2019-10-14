import asyncio
import csv
from io import BytesIO, StringIO
import logging
import os
import tempfile
import zipfile

import model_registry


MODEL_EXE = os.environ.get("WQDSS_MODEL_EXE", "/dss-bin/w2_exe_linux_par")
DEFAULT_MODEL = "default"

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)


def prepare_run_dir(exec_id, param_values, model_name, model_registry_client):
    '''
    Populates a temporary directory with the model files,
    along with inputs provided by the user
    '''

    run_dir = tempfile.mkdtemp(prefix=f'wqdss-exec-{exec_id}')
    os.rmdir(run_dir)

    logger.info("going to get model by name")
    model_contents = model_registry_client.get_model_by_name(model_name)
    model_zip = zipfile.ZipFile(BytesIO(model_contents))
    model_zip.extractall(run_dir)
    update_inputs_for_run(run_dir, param_values)
    return run_dir


def update_inputs_for_run(run_dir, input_values):
    # for each file in params that should be updated:
    input_files = input_values.files
    for i in input_files:
        # read the first contents of the input
        with open(os.path.join(run_dir, i), 'r') as ifile:
            contents = ifile.readlines()

        # copy 2 header lines, and for the rest update the contents of the QWD value
        reader = csv.DictReader(contents[2:])
        with open(os.path.join(run_dir, i), 'w') as ofile:
            ofile.writelines(contents[:2])
            writer = csv.DictWriter(ofile, reader.fieldnames)
            out_param = input_values.columns[i]
            for row in reader:
                row[out_param] = input_values.values[i]
                writer.writerow(row)


async def exec_model_async(run_dir):
    process = await asyncio.create_subprocess_exec(
        MODEL_EXE, run_dir,
        stdin=asyncio.subprocess.DEVNULL, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
    logger.info(f'going to execute process {process}')
    await process.wait()
    logger.info(f'Finished executing {process}')


def get_out_file_contents(run_dir, out_file):
    with open(os.path.join(run_dir, out_file), 'r') as ifile:
        contents = ifile.readlines()
    return contents


def create_run_zip(run_dir, files):
    zipbytes = BytesIO()
    with zipfile.ZipFile(zipbytes, 'w') as run_zip:
        for in_file in files:
            run_zip.write(os.path.join(run_dir, in_file), in_file)

    return zipbytes.getvalue()


class RemoteModelExecution:

    def __init__(self, model_name):
        # TODO: remove this, this should be on the actual execution side
        # TODO: add persistence
        self.model_registry_client = model_registry.ModelRegistryClient()
        self.model_name = model_name
        self.runs = {}

    async def _prepare_run_dir(self, exec_id, param_values):
        # TODO: calls to model_execution should be transformed into celery tasks
        return prepare_run_dir(exec_id, param_values, self.model_name, self.model_registry_client)

    async def _exec_model_async(self, run_dir):
        # TODO: calls to model_execution should be transformed into celery tasks
        return await exec_model_async(run_dir)

    async def _create_run_zip(self, run_dir, files):
        return BytesIO(create_run_zip(run_dir, files))

    def get_out_contents(self, run_zip, output_file):
        out_as_zip_file = zipfile.ZipFile(run_zip)
        file_contents = out_as_zip_file.read(output_file).decode()
        return StringIO(file_contents).readlines()

    async def run(self, exec_id, run_id, param_values, output_file):
        logger.info("going to create run_dir")
        run_dir = await self._prepare_run_dir(exec_id, param_values)
        logger.info(f"done creating run_dir {run_dir}")
        await self._exec_model_async(run_dir)
        logger.info(f"done executing model {run_dir}")
        self.runs[run_id] = await self._create_run_zip(run_dir, list(param_values.files) + [output_file])

        return self.get_out_contents(self.runs[run_id], output_file)

    def get_run_zip(self, run_id):
        return self.runs[run_id]
