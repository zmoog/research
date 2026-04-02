@description('Azure region for all resources')
param location string = resourceGroup().location

@description('Base name for all resources')
param baseName string = 'ecf-aca'

@description('Event Hub namespace SKU')
@allowed(['Standard', 'Premium'])
param eventHubSku string = 'Standard'

@description('Container image to deploy')
param containerImage string

@description('Elasticsearch OTLP endpoint')
param elasticsearchOtlpEndpoint string

@description('Elasticsearch API key')
@secure()
param elasticsearchApiKey string

@description('Minimum number of replicas')
param minReplicas int = 1

@description('Maximum number of replicas')
param maxReplicas int = 3

// ---------- Container Registry ----------

resource acr 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: replace('${baseName}acr', '-', '')
  location: location
  sku: {
    name: 'Basic'
  }
  properties: {
    adminUserEnabled: true
  }
}

// ---------- Event Hub Namespace + Hubs ----------
// Kafka protocol requires Standard tier or above.

resource eventHubNamespace 'Microsoft.EventHub/namespaces@2024-01-01' = {
  name: '${baseName}-ehns'
  location: location
  sku: {
    name: eventHubSku
    tier: eventHubSku
    capacity: 1
  }
  properties: {
    kafkaEnabled: true
  }
}

resource logsHub 'Microsoft.EventHub/namespaces/eventhubs@2024-01-01' = {
  parent: eventHubNamespace
  name: 'logs'
  properties: {
    partitionCount: 4
    messageRetentionInDays: 1
  }
}

resource logsConsumerGroup 'Microsoft.EventHub/namespaces/eventhubs/consumergroups@2024-01-01' = {
  parent: logsHub
  name: 'ecf'
}

resource metricsHub 'Microsoft.EventHub/namespaces/eventhubs@2024-01-01' = {
  parent: eventHubNamespace
  name: 'metrics'
  properties: {
    partitionCount: 4
    messageRetentionInDays: 1
  }
}

resource metricsConsumerGroup 'Microsoft.EventHub/namespaces/eventhubs/consumergroups@2024-01-01' = {
  parent: metricsHub
  name: 'ecf'
}

// Shared access policy with Listen permission for the Kafka consumer.
// The connection string from this policy is used as the SASL password.
resource listenRule 'Microsoft.EventHub/namespaces/authorizationRules@2024-01-01' = {
  parent: eventHubNamespace
  name: 'ecf-listen'
  properties: {
    rights: [
      'Listen'
    ]
  }
}

// Shared access policy with Send permission for testing (send test messages).
resource sendRule 'Microsoft.EventHub/namespaces/authorizationRules@2024-01-01' = {
  parent: eventHubNamespace
  name: 'ecf-send'
  properties: {
    rights: [
      'Send'
    ]
  }
}

// ---------- Log Analytics (for ACA environment) ----------

resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: '${baseName}-logs'
  location: location
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
  }
}

// ---------- Container Apps Environment ----------

resource containerAppsEnv 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: '${baseName}-env'
  location: location
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalytics.properties.customerId
        sharedKey: logAnalytics.listKeys().primarySharedKey
      }
    }
  }
}

// ---------- Container App ----------

resource containerApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: '${baseName}-app'
  location: location
  properties: {
    managedEnvironmentId: containerAppsEnv.id
    configuration: {
      activeRevisionsMode: 'Single'
      registries: [
        {
          server: acr.properties.loginServer
          username: acr.listCredentials().username
          passwordSecretRef: 'acr-password'
        }
      ]
      secrets: [
        {
          name: 'acr-password'
          value: acr.listCredentials().passwords[0].value
        }
        {
          name: 'elasticsearch-api-key'
          value: elasticsearchApiKey
        }
        {
          name: 'eventhub-connection-string'
          value: listenRule.listKeys().primaryConnectionString
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'otelcol'
          image: containerImage
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
          env: [
            { name: 'EVENTHUB_NAMESPACE', value: '${eventHubNamespace.name}.servicebus.windows.net' }
            { name: 'EVENTHUB_LOGS_NAME', value: 'logs' }
            { name: 'EVENTHUB_METRICS_NAME', value: 'metrics' }
            { name: 'EVENTHUB_CONSUMER_GROUP', value: 'ecf' }
            { name: 'EVENTHUB_CONNECTION_STRING', secretRef: 'eventhub-connection-string' }
            { name: 'ELASTICSEARCH_OTLP_ENDPOINT', value: elasticsearchOtlpEndpoint }
            { name: 'ELASTICSEARCH_API_KEY', secretRef: 'elasticsearch-api-key' }
          ]
        }
      ]
      scale: {
        minReplicas: minReplicas
        maxReplicas: maxReplicas
      }
    }
  }
}

// ---------- Outputs ----------

output containerAppName string = containerApp.name
output eventHubNamespaceName string = eventHubNamespace.name
output acrLoginServer string = acr.properties.loginServer
output sendConnectionString string = sendRule.listKeys().primaryConnectionString
