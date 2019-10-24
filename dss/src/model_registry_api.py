import os

import responder
import logging

import wq2dss
import wq2dss.model_registry

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

api = responder.API()


@api.on_event('startup')
async def load_models():
    wq2dss.model_registry.load_models()


@api.route("/models/{name}")
async def get_model_by_name(req, resp, *, name):
    try:
        resp.content = wq2dss.model_registry.get_model_by_name(name)
        resp.mimetype = "application/zip"
    except wq2dss.model_registry.ModelNotFoundError:
        resp.status_code = api.status_codes.not_found


@api.route("/models")
class ModelsResource:
    async def on_get(self, req, resp):
        '''
        Return all models currently registered
        '''
        resp.media = {"models": list(wq2dss.model_registry.get_models())}
        logging.info('returned model list')

    async def on_post(self, req, resp):
        """
        Upload a directory containing a calibrated model, receives an identifier for that model
        """
        files = await req.media('files')
        model_contents = files['model']['content']
        model_name = files['model']['filename']
        wq2dss.model_registry.add_model(model_name, model_contents)
        logger.info("Added model %s", model_name)
        resp.media = {"model_name": model_name}


if __name__ == "__main__":
    logger.info("app started!")
    debug = os.environ.get("DEBUG", False)
    log_level = 'debug' if debug else 'info'
    if debug:
        log_level = 'debug'

    # add rendering of index.html as the default route
    api.run(debug=debug, log_level=log_level)
