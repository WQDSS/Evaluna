from io import BytesIO
import logging
import pathlib
import os
import shutil
import zipfile

import requests

MODELS = {}
BASE_MODEL_DIR = os.environ.get("WQDSS_BASE_MODEL_DIR", "/models")
MODEL_REGISTRY_SERVICE = os.environ.get("MODEL_REGISTRY_SERVICE", "model-registry")

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)


class ModelNotFoundError(Exception):
    def __init__(self, model_name):
        self.model_name = model_name
        super().__init__(f'model_name id: {model_name} not registered')


def load_models():
    '''
    Populate the models DB, currently by walking the models directory
    '''

    models = next(os.walk(BASE_MODEL_DIR))[1]
    for model in models:
        logger.info(f"Loading model {model}")
        MODELS[model] = os.path.join(BASE_MODEL_DIR, model)
        if not os.path.exists(f"{MODELS[model]}.zip"):
            # if the zip archive doesn't exist - create it
            shutil.make_archive(MODELS[model], "zip", MODELS[model])


def get_model_by_name(model_name):
    try:
        model_zip = f"{MODELS[model_name]}.zip"
        with open(model_zip, "rb") as model_contents:
            return model_contents.read()
    except KeyError:
        raise ModelNotFoundError(model_name)


def _common_subdir_in_zip(model_zip):
    """Given a zip file, return the common_subdir that all files have (if there is one)."""

    # get the names of all files (not directories)
    namelist = [f.filename for f in model_zip.infolist() if not f.is_dir()]
    if not namelist:
        return None

    parts = pathlib.PurePath(namelist[0]).parts
    same_parts = []

    # loop through all parts (except final one, since that's the file name)
    # and confirm they are the same for all files
    for part_num, part in enumerate(parts[:-1]):
        if all(pathlib.PurePath(name).parts[part_num] == part for name in namelist):
            same_parts.append(part)
        else:
            break

    if same_parts:
        return pathlib.PurePath(*same_parts)

    return None


def add_model(model_name, model_contents, ignore_already_exists=True):
    logger.info(f"going to add model {model_name}")
    if model_name in MODELS:
        msg = f"model {model_name} already exists in DB"
        if ignore_already_exists:
            logger.warning(msg)
            return
        raise Exception(msg)

    model_dir = os.path.join(BASE_MODEL_DIR, model_name)
    model_zip = zipfile.ZipFile(BytesIO(model_contents))
    model_zip.extractall(model_dir)

    # if there was a hierarchy of directories in the zip (but all files are in the same path)
    # use only the contents of the leaf directory
    common_subdir = _common_subdir_in_zip(model_zip)
    if common_subdir:
        logger.debug(f'found common subdir {common_subdir}, going to take files from it')
        full_dir = os.path.join(model_dir, common_subdir)
        for f in os.listdir(full_dir):
            shutil.move(os.path.join(full_dir, f), model_dir)
        shutil.rmtree(os.path.join(model_dir, common_subdir.parts[0]))

    else:
        logger.debug('no common subidr was found')
    MODELS[model_name] = model_dir

    # create a zip file that will be returned upon request
    shutil.make_archive(os.path.join(BASE_MODEL_DIR, model_name), 'zip', model_dir)


def get_models():
    for m in MODELS:
        yield m


class ModelRegistryClient:

    def __init__(self, uri=f"http://{MODEL_REGISTRY_SERVICE}:80/models", requests_mod=None):
        self.uri = uri
        self.requests = requests_mod or requests

    def get_model_by_name(self, model_name):
        try:
            logger.info(f"going to get from {self.uri}/{model_name}")
            response = self.requests.get(f"{self.uri}/{model_name}")
            response.raise_for_status()
            return response.content
        except self.requests.HTTPError:
            if response.status_code == 404:
                raise ModelNotFoundError(model_name)
            else:
                raise

    def get_models(self):
        return self.requests.get(f"{self.uri}").json()

    def add_model(self, model_name, model_contents):
        files = {'model': (model_name, model_contents, 'application/zip')}
        return self.requests.post(f"{self.uri}", files=files).json()
