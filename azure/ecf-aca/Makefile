IMAGE_NAME ?= ecf-aca-collector
IMAGE_TAG ?= dev
BASE_NAME ?= ecf-aca

RESOURCE_GROUP ?= $(BASE_NAME)-rg
LOCATION ?= eastus2

.PHONY: build tidy docker-build deploy push logs send-test-event clean

# ---------- Local ----------

build:
	cd collector && CGO_ENABLED=0 go build -o ../bin/collector .

tidy:
	cd collector && go mod tidy

run: build
	./bin/collector --config config.yaml

# ---------- Infrastructure ----------

deploy:
	az group create --name $(RESOURCE_GROUP) --location $(LOCATION)
	az deployment group create \
		--resource-group $(RESOURCE_GROUP) \
		--template-file infra/main.bicep \
		--parameters baseName=$(BASE_NAME) \
		--parameters containerImage=mcr.microsoft.com/azuredocs/containerapps-helloworld:latest \
		--query 'properties.outputs' -o json

# ---------- Build & Push Image ----------

docker-build:
	docker build --platform linux/amd64 -t $(IMAGE_NAME):$(IMAGE_TAG) .

push: docker-build
	$(eval ACR := $(shell az deployment group show \
		--resource-group $(RESOURCE_GROUP) \
		--name main \
		--query 'properties.outputs.acrLoginServer.value' -o tsv))
	az acr login --name $(ACR)
	docker tag $(IMAGE_NAME):$(IMAGE_TAG) $(ACR)/$(IMAGE_NAME):$(IMAGE_TAG)
	docker push $(ACR)/$(IMAGE_NAME):$(IMAGE_TAG)

# ---------- Update App with Real Image ----------

update: push
	$(eval ACR := $(shell az deployment group show \
		--resource-group $(RESOURCE_GROUP) \
		--name main \
		--query 'properties.outputs.acrLoginServer.value' -o tsv))
	az deployment group create \
		--resource-group $(RESOURCE_GROUP) \
		--template-file infra/main.bicep \
		--parameters baseName=$(BASE_NAME) \
		--parameters containerImage=$(ACR)/$(IMAGE_NAME):$(IMAGE_TAG) \
		--query 'properties.outputs' -o json

# ---------- Observe ----------

logs:
	az containerapp logs show \
		--resource-group $(RESOURCE_GROUP) \
		--name $(BASE_NAME)-app \
		--type console \
		--follow

# ---------- Test ----------

send-test-event:
	$(eval EHNS := $(shell az deployment group show \
		--resource-group $(RESOURCE_GROUP) \
		--name main \
		--query 'properties.outputs.eventHubNamespaceName.value' -o tsv))
	$(eval SEND_CONN := $(shell az deployment group show \
		--resource-group $(RESOURCE_GROUP) \
		--name main \
		--query 'properties.outputs.sendConnectionString.value' -o tsv))
	EVENTHUB_NAMESPACE=$(EHNS).servicebus.windows.net \
	EVENTHUB_CONNECTION_STRING="$(SEND_CONN)" \
	python3 scripts/send-test-event.py

# ---------- Clean up ----------

clean:
	rm -rf bin/
	az group delete --name $(RESOURCE_GROUP) --yes --no-wait
