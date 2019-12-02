function setup(modelFormElement, selectElement, formElement, resultElement) {
  formElement.addEventListener("submit", function(event) {
    event.preventDefault();
    executeDss(formElement);
  });

  modelFormElement.addEventListener("submit", function(event) {
    event.preventDefault();
    uploadModel(modelFormElement);
  });

  // create closures to wrap updates
  function updateResults(e) {
    dssUpdate(resultElement, e);
  }

  function updateModelList(e) {
    populateModelsInselect(selectElement).then(elem => {
      M.FormSelect.init(elem, {});
    });
  }

  formElement.addEventListener("dssUpdate", updateResults);
  modelFormElement.addEventListener("modelUpdate", updateModelList);
  updateModelList();
}

function populateModelsInselect(selectElement) {
  return fetch("models")
    .then(response => response.json())
    .then(data => {
      console.log(data);
      selectElement.options.length = 0; // clear any previous options

      data["models"].forEach((element, key) => {
        selectElement[key] = new Option(element, element);
      });

      // set to a null value
      selectElement.value = null;
      return selectElement;
    });
}

function createExecutionListItem(execution) {
  const li = document.createElement("li");
  li.innerHTML = JSON.stringify(execution);
  return li;
}

function fetchPreviousResults(executionsListElement) {
  return fetch("executions")
    .then(response => response.json())
    .then(data => {
      console.log(data);
      data["executions"].forEach(execution => {
        executionsListElement.appendChild(createExecutionListItem(execution));
      });
    });
}

function executeDss(form) {
  var formData = new FormData(form);
  console.log(form);
  console.log(formData);
  fetch("dss", {
    method: "POST",
    body: formData
  })
    .then(r => {
      console.log(r);
      return r;
    })
    .then(response => response.json())
    .then(data => {
      console.log(data);
      monitorExecution(data["id"], form);
    });
}

function monitorExecution(executionId, form) {
  function monitorThis() {
    fetch(`status/${executionId}`)
      .then(response => response.json())
      .then(data => {
        console.log(data);
        if (data["status"] === "COMPLETED") {
          console.log("Processing is complete");
          data["link"] = `best_run/${executionId}`;
        } else {
          setTimeout(monitorThis, 5000);
        }
        form.dispatchEvent(new CustomEvent("dssUpdate", { detail: data }));
      })
      .catch(reason => {
        console.log(`Error while checking status ${reason}`);
        setTimeout(monitorThis, 5000);
      });
  }
  monitorThis();
}

function dssUpdate(resultElement, e) {
  let execResult = resultElement.querySelector(`#result-${e.detail.id}`);

  // if the result block doesn't exist yet, create it and append to overall results
  if (execResult === null) {
    execResult = document.createElement("div");
    execResult.setAttribute("id", `result-${e.detail.id}`);
    resultElement.appendChild(execResult);
  }

  execResult.innerHTML = `<pre>${JSON.stringify(e.detail, undefined, 2)}</pre>`;
  if (e.detail.status == "RUNNING") {
    execResult.innerHTML += `<div class="progress"><div class="indeterminate"></div></div>`;
  }
  if (e.detail.link !== undefined) {
    execResult.innerHTML += `<a href=${e.detail.link}>best run</a>`;
  }

  // auto-scroll to the bottom of the results
  resultElement.scrollTop = resultElement.scrollHeight;
}

function uploadModel(modelFormElement) {
  var formData = new FormData(modelFormElement);
  fetch("models", {
    method: "POST",
    body: formData
  })
    .then(response => response.json())
    .then(data => {
      console.log(data);
      modelFormElement.dispatchEvent(
        new CustomEvent("modelUpdate", { detail: data })
      );
    });
}
