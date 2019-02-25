import json

import responder
import processing

api = responder.API()

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
        print(result)

@api.route("/dss")
async def exec_dss(req, resp):
    """
    Get the uploaded file, execute the dss in the background (multiple executions of the model)
    """    
    params = json.loads((await req.media('files'))['input']['content'])

    exec_id = processing.get_exec_id()
    
    @api.background.task
    def task():        
        processing.execute_dss(exec_id, params)
    
    task()
    resp.media = {"id" : exec_id}

if __name__ == "__main__":
    api.run()