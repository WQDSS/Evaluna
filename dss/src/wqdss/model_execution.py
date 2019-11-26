import asyncio
import csv
from io import BytesIO, StringIO
import logging
import os
import subprocess
import tempfile
import zipfile

MODEL_EXE = os.environ.get("WQDSS_MODEL_EXE", "/dss-bin/w2_exe_linux_par")
DEFAULT_MODEL = "default"

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)


def prepare_run_dir(param_values, model_contents):
    '''
    Populates a temporary directory with the model files,
    along with inputs provided by the user
    '''

    run_dir = tempfile.mkdtemp(prefix=f'wqdss-exec')
    os.rmdir(run_dir)

    logger.info("going to get model by name")
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


def exec_model(run_dir):
    process = subprocess.Popen([MODEL_EXE, run_dir], stdin=subprocess.DEVNULL,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    logger.info(f'going to execute process {process}')
    process.wait()
    logger.info(f'Finished executing {process}')


def get_out_contents(run_zip, output_file):
    out_as_zip_file = zipfile.ZipFile(BytesIO(run_zip))
    file_contents = out_as_zip_file.read(output_file).decode()
    return StringIO(file_contents).readlines()


def create_run_zip(run_dir, files):
    zipbytes = BytesIO()
    with zipfile.ZipFile(zipbytes, 'w') as run_zip:
        for in_file in files:
            run_zip.write(os.path.join(run_dir, in_file), in_file)

    return zipbytes.getvalue()


class ModelExecutionPermutation:

    def __init__(self, input_files, columns, values):
        self.files = input_files
        self.columns = dict(zip(self.files, columns))
        self.values = dict(zip(self.files, values))

    def as_dict(self):
        return {
            "files": list(self.files),
            "columns": list(self.columns.values()),
            "values": list(self.values.values())
        }

    @classmethod
    def from_dict(cls, d):
        return cls(d["files"], d["columns"], d["values"])
