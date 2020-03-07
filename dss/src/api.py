import asyncio
import json
import os

import responder
import logging

import wqdss.model_registry
import wqdss.processing

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)


api = responder.API()
model_registry_client = wqdss.model_registry.ModelRegistryClient()


@api.route("/status/{exec_id}")
async def status(req, resp, *, exec_id):
    try:
        status = wqdss.processing.get_status(exec_id)
        result = wqdss.processing.get_result(exec_id)
    except KeyError:
        status = "NOT_FOUND"
        result = None

    resp.media = {"id": exec_id, "status": status}
    if result is not None:
        try:
            logger.info(f"Got Result {result}")
            result_copy = []
            for iteration_result in result:
                logger.info(f"got iteration_result: {iteration_result}")
                iter_copy = dict(iteration_result)
                if "params" in iteration_result:
                    iter_copy["params"] = iteration_result["params"].values
                result_copy.append(iter_copy)

            resp.media["result"] = result_copy
            logger.info(result)
        except Exception as e:
            resp.media["result"] = str(e)


@api.route("/best_run/{exec_id}")
async def run_zip(req, resp, *, exec_id):
    try:
        status = wqdss.processing.get_status(exec_id)
        if status != "COMPLETED":
            raise KeyError

        resp.content = wqdss.processing.get_best_run(exec_id)
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

    exec_id = wqdss.processing.get_exec_id()

    @api.background.task
    def dss_task(loop):
        logger.info("Going to execute dss!")
        loop.create_task(wqdss.processing.execute_dss(exec_id, params))

    dss_task(asyncio.get_running_loop())
    logger.info("created task %s", exec_id)
    resp.media = {"id": exec_id}


@api.route("/executions")
async def completed_executions(req, resp):
    logger.info("fetching previous executions")
    resp.media = wqdss.processing.get_executions()


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
