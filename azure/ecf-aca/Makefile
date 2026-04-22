DOCKER_USERNAME ?= mauriziobranca626
IMAGE_NAME ?= cloud-forwarder-aca
IMAGE_TAG ?= dev
FULL_IMAGE_NAME = $(DOCKER_USERNAME)/$(IMAGE_NAME):$(IMAGE_TAG)
BASE_NAME ?= cloud-forwarder-aca

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
		--parameters containerImage=$(FULL_IMAGE_NAME) \
		--query 'properties.outputs' -o json

# ---------- Build & Push Image ----------

docker-build:
	docker build --platform linux/amd64 -t $(IMAGE_NAME):$(IMAGE_TAG) .

push: docker-build
	docker tag $(IMAGE_NAME):$(IMAGE_TAG) $(FULL_IMAGE_NAME)
	docker push $(FULL_IMAGE_NAME)

# ---------- Update App with Real Image ----------

update: push
	az deployment group create \
		--resource-group $(RESOURCE_GROUP) \
		--template-file infra/main.bicep \
		--parameters baseName=$(BASE_NAME) \
		--parameters containerImage=$(FULL_IMAGE_NAME) \
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
