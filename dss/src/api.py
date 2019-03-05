import asyncio
import json
import os

import responder
import processing
import logging

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)


api = responder.API()

@api.on_event('startup')
async def load_models():
    processing.load_models()

@api.route("/status/{exec_id}")
async def status(req, resp, * , exec_id):
    try:
        status = processing.get_status(exec_id)
        result = processing.get_result(exec_id)
    except KeyError:
        status = "NOT_FOUND"
        result = None

    resp.media = {"id" : exec_id, "status": status}    
    if result is not None:
        resp.media["result"] = result
        logging.info(result)

@api.route("/dss")
async def exec_dss(req, resp):
    """
    Get the uploaded file, execute the dss in the background (multiple executions of the model)
    """    
    params = json.loads((await req.media('files'))['input']['content'])


    exec_id = processing.get_exec_id()    
        
    async def dss_task():
        logger.info("Going to execute dss!")       
        await processing.execute_dss(exec_id, params)
    
    loop = asyncio.get_event_loop()
    loop.create_task(dss_task())
    logger.info("created task %s", exec_id)
    resp.media = {"id" : exec_id}

@api.route("/add-model")
async def add_model(req, resp)    :
    """
    Upload a directory containing a calibrated model, receives an identifier for that model
    """
    files = await req.media('files')
    model_contents = files['model']['content']    
    model_name = files['model']['filename']
    processing.add_model(model_name, model_contents)
    logger.info("Added model %s", model_name)
    resp.media = {"model_name" : model_name}

if __name__ == "__main__":
    logger.info("app started!")
    debug = os.environ.get("DEBUG", False)
    log_level = 'debug' if debug else 'info'
    if debug:
        log_level='debug'
    api.run(debug=debug, log_level=log_level)

