import asyncio
import json
import os

import responder
import logging

import wq2dss.model_registry
import wq2dss.processing

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)


api = responder.API()
model_registry_client = wq2dss.model_registry.ModelRegistryClient()


@api.route("/status/{exec_id}")
async def status(req, resp, *, exec_id):
    try:
        status = wq2dss.processing.get_status(exec_id)
        result = wq2dss.processing.get_result(exec_id)
    except KeyError:
        status = "NOT_FOUND"
        result = None

    resp.media = {"id": exec_id, "status": status}
    if result is not None:
        result_copy = dict(result)
        result_copy["params"] = result["params"].values
        resp.media["result"] = result_copy
        logging.info(result)


@api.route("/best_run/{exec_id}")
async def run_zip(req, resp, *, exec_id):
    try:
        status = wq2dss.processing.get_status(exec_id)
        if status != "COMPLETED":
            raise KeyError

        resp.content = wq2dss.processing.get_best_run(exec_id)
        resp.mimetype = "application/zip"
    except KeyError:
        resp.status_code = 400
        resp.media = {'exec_id': exec_id}


@api.route("/dss")
async def exec_dss(req, resp):
    """
    Get the uploaded file, execute the dss in the background (multiple executions of the model)
    """
    logger.info("got a request for executing a dss")
    media = await req.media('files')
    logger.debug("%s", str(media))
    params = json.loads(media['input']['content'])
    if 'model_name' in media:
        params['model_run']['model_name'] = media['model_name'].decode()

    exec_id = wq2dss.processing.get_exec_id()

    async def dss_task():
        logger.info("Going to execute dss!")
        await wq2dss.processing.execute_dss(exec_id, params)

    loop = asyncio.get_event_loop()
    loop.create_task(dss_task())
    logger.info("created task %s", exec_id)
    resp.media = {"id": exec_id}


@api.route("/models")
class ModelsResource:
    '''Forwarding the models resource to the dedicated micro-service'''

    def on_get(self, req, resp):
        '''
        Return all models currently registered
        '''
        resp.media = model_registry_client.get_models()

    async def on_post(self, req, resp):
        """
        Upload a directory containing a calibrated model, receives an identifier for that model
        """
        files = await req.media('files')
        model_contents = files['model']['content']
        model_name = files['model']['filename']
        resp.media = model_registry_client.add_model(model_name, model_contents)


if __name__ == "__main__":
    logger.info("app started!")
    debug = os.environ.get("DEBUG", False)
    log_level = 'debug' if debug else 'info'
    if debug:
        log_level = 'debug'

    # add rendering of index.html as the default route
    api.add_route("/", static=True)
    api.run(debug=debug, log_level=log_level)
