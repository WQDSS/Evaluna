from io import BytesIO
import logging
import os
import shutil
import zipfile

import requests

MODELS = {}
BASE_MODEL_DIR = os.environ.get("WQDSS_BASE_MODEL_DIR", "/models")

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
        MODELS[model] = os.path.join(BASE_MODEL_DIR, model)
        if not os.path.exists(f"{MODELS[model]}.zip"):
            # if the zip archive doesn't exist - create it
            shutil.make_archive(MODELS[model], "zip", MODELS[model])


def get_model_by_name(model_name):
    try:
        # model_dir = MODELS[model_name]
        model_zip = f"{MODELS[model_name]}.zip"
        with open(model_zip, "rb") as model_contents:
            return model_contents.read()
    except KeyError:
        raise ModelNotFoundError(model_name)


def add_model(model_name, model_contents):
    if model_name in MODELS:
        raise Exception(f"model {model_name} already exists in DB")

    model_dir = os.path.join(BASE_MODEL_DIR, model_name)
    model_zip = zipfile.ZipFile(BytesIO(model_contents))
    model_zip.extractall(model_dir)
    MODELS[model_name] = model_dir

    with open(os.path.join(BASE_MODEL_DIR, f"{model_name}.zip"), "wb") as model_file:
        model_file.write(model_contents)


def get_models():
    for m in MODELS:
        yield m


class ModelRegistryClient:

    def __init__(self, uri="http://model-registry:80/models", requests_mod=None):
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
        return self.requests.post("/models", files=files).json()
