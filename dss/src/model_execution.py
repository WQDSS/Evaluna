import asyncio
import csv
from io import BytesIO
import logging
import os
import tempfile
import zipfile

import model_registry

MODEL_EXE = os.environ.get("WQDSS_MODEL_EXE", "/dss-bin/w2_exe_linux_par")

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)


class ModelDirNotFoundError(Exception):
    def __init__(self, model_dir):
        self.model_dir = model_dir
        super().__init__(f'Model dir: {model_dir} not found')


def prepare_run_dir(exec_id, param_values, model_name):
    '''
    Populates a temporary directory with the model files,
    along with inputs provided by the user
    '''

    run_dir = tempfile.mkdtemp(prefix=f'wqdss-exec-{exec_id}')
    os.rmdir(run_dir)

    try:
        model_contents = model_registry.get_model_by_name(model_name)
        model_zip = zipfile.ZipFile(BytesIO(model_contents))
        model_zip.extractall(run_dir)
        update_inputs_for_run(run_dir, param_values)
    except FileNotFoundError:
        raise ModelDirNotFoundError(model_name)

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


async def exec_model_async(run_dir, output_file):
    process = await asyncio.create_subprocess_exec(
        MODEL_EXE, run_dir,
        stdin=asyncio.subprocess.DEVNULL, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
    logger.debug(f'going to execute process {process}')
    await process.wait()
    logger.debug(f'Finished executing {process}')
    return get_out_file_contents(run_dir, output_file)


def get_out_file_contents(run_dir, out_file):
    with open(os.path.join(run_dir, out_file), 'r') as ifile:
        contents = ifile.readlines()
    return contents
