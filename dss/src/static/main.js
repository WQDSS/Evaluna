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
    populateModelsInselect(selectElement);
  }

  formElement.addEventListener("dssUpdate", updateResults);
  modelFormElement.addEventListener("modelUpdate", updateModelList);
  updateModelList();
}

function populateModelsInselect(selectElement) {
  fetch("models")
    .then(response => response.json())
    .then(data => {
      console.log(data);
      selectElement.options.length = 0; // clear any previous options

      data["models"].forEach((element, key) => {
        selectElement[key] = new Option(element, element);
      });

      // set to a null value
      selectElement.value = null;
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
      });
  }
  monitorThis();
}

function dssUpdate(resultElement, e) {
  resultElement.innerHTML += `<pre>${JSON.stringify(e.detail)}</pre>`;
  if (e.detail.link !== undefined) {
    resultElement.innerHTML += `<a href=${e.detail.link}>best run</a>`;
  }
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
