function setup(selectElement, formElement, resultElement) {
    populateModelsInselect(selectElement)
    formElement.addEventListener("submit", function (event) {
        event.preventDefault();
        executeDss(formElement);
    });

    // create a closure to wrap updates
    function updateResults(e) {
        dssUpdate(resultElement, e)
    }
    formElement.addEventListener('dssUpdate', updateResults)
}

function populateModelsInselect(selectElement) {    
    fetch('models')
        .then(response => response.json())
        .then((data) => {
            console.log(data)            
            data["models"].forEach((element, key) => {
                selectElement[key] = new Option(element, element)
            });
            
            // set to a null value
            selectElement.value = null
        })
}


function executeDss(form) {
    var formData = new FormData(form)
    console.log(form)
    console.log(formData)
    fetch('dss', {
            method: 'POST',
            body: formData})
        .then(response => response.json())
        .then((data) => {
            console.log(data)
            monitorExecution(data['id'], form)
        })
}

function monitorExecution(executionId, form) {
    function monitorThis() {
        fetch(`status/${executionId}`)
            .then(response => response.json())
            .then((data) => {
                console.log(data)                
                if (data['status'] === 'COMPLETED') {
                    console.log("Processing is complete")
                } else {                    
                    setTimeout(monitorThis, 5000)
                }
                form.dispatchEvent(new CustomEvent("dssUpdate", { detail: data }))
            })
    }
    monitorThis()
}

function dssUpdate(resultElement, e) {
    resultElement.innerHTML += `<pre>${JSON.stringify(e.detail)}</pre>`

}