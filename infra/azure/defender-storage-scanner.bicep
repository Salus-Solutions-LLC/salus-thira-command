targetScope = 'resourceGroup'

@description('Environment whose untrusted uploads are scanned.')
@allowed([
  'dev'
  'prod'
])
param environmentName string

@description('Existing SalCAPA deployment suffix; keeps scanner names tied to the governed environment.')
@minLength(4)
@maxLength(6)
param uniqueSuffix string

@description('Must match the region of the governed SalCAPA environment and scan-result topic.')
@allowed([
  'eastus2'
  'southcentralus'
])
param location string

@description('Explicit monthly GB scanning cap. Reaching it leaves new objects quarantined, not clean. Azure can exceed the cap by up to 20 GB.')
@minValue(1)
@maxValue(100)
param scanCapGbPerMonth int

@description('Exact reviewed source commit for the scanner installation.')
@minLength(40)
@maxLength(40)
param sourceCommit string

@description('Recorded scanner approval and updated spend authority.')
param approvalRecord string

var stem = 'salcapa-${environmentName}-${uniqueSuffix}'
var accountName = replace('${stem}-scan', '-', '')

// This is a dedicated DMZ account. The application must never serve content
// from its quarantine container; only an authenticated, exact-object Clean
// result may authorize a separate copy into the governed evidence account.
resource quarantineStorage 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: accountName
  location: location
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
  tags: {
    system: 'SalCAPA'
    environment: environmentName
    purpose: 'untrusted-upload-malware-quarantine'
    approvalRecord: approvalRecord
    sourceCommit: sourceCommit
  }
  properties: {
    allowBlobPublicAccess: false
    allowSharedKeyAccess: false
    defaultToOAuthAuthentication: true
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
  }
}

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' = {
  parent: quarantineStorage
  name: 'default'
  properties: {
    deleteRetentionPolicy: {
      enabled: true
      days: 14
    }
    containerDeleteRetentionPolicy: {
      enabled: true
      days: 14
    }
    isVersioningEnabled: true
  }
}

resource quarantineContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobService
  name: 'quarantine'
  properties: {
    publicAccess: 'None'
  }
}

resource queueService 'Microsoft.Storage/storageAccounts/queueServices@2023-05-01' = {
  parent: quarantineStorage
  name: 'default'
}

resource scanResultsQueue 'Microsoft.Storage/storageAccounts/queueServices/queues@2023-05-01' = {
  parent: queueService
  name: 'scan-results'
}

// Defender requires a same-region Event Grid topic reachable on public IPs.
// A queue processor must be installed and tested before any Protected Member
// upload is sent to this account.
resource resultTopic 'Microsoft.EventGrid/topics@2022-06-15' = {
  name: '${stem}-scan-results'
  location: location
  identity: {
    type: 'SystemAssigned'
  }
  tags: {
    system: 'SalCAPA'
    environment: environmentName
    approvalRecord: approvalRecord
    sourceCommit: sourceCommit
  }
  properties: {
    inputSchema: 'EventGridSchema'
    publicNetworkAccess: 'Enabled'
  }
}

// The Event Grid topic may add messages only to this scan-result queue.
// It does not receive blob data permissions or account keys.
var queueMessageSenderRole = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'c6a89b2d-59bc-44d0-9896-0f6e12d7b80a')
resource topicQueueSender 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(scanResultsQueue.id, resultTopic.id, queueMessageSenderRole)
  scope: scanResultsQueue
  properties: {
    roleDefinitionId: queueMessageSenderRole
    principalId: resultTopic.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

resource resultSubscription 'Microsoft.EventGrid/topics/eventSubscriptions@2022-06-15' = {
  parent: resultTopic
  name: 'scan-results-to-queue'
  properties: {
    eventDeliverySchema: 'EventGridSchema'
    deliveryWithResourceIdentity: {
      identity: {
        type: 'SystemAssigned'
      }
      destination: {
        endpointType: 'StorageQueue'
        properties: {
          resourceId: quarantineStorage.id
          queueName: scanResultsQueue.name
          queueMessageTimeToLiveInSeconds: 604800
        }
      }
    }
    filter: {
      includedEventTypes: [
        'Microsoft.Security.MalwareScanningResult'
      ]
    }
    retryPolicy: {
      maxDeliveryAttempts: 30
      eventTimeToLiveInMinutes: 1440
    }
  }
  dependsOn: [
    topicQueueSender
  ]
}

resource defenderScanner 'Microsoft.Security/defenderForStorageSettings@2025-06-01' = {
  scope: quarantineStorage
  name: 'current'
  properties: {
    isEnabled: true
    overrideSubscriptionLevelSettings: true
    malwareScanning: {
      blobScanResultsOptions: 'None'
      onUpload: {
        isEnabled: true
        capGBPerMonth: scanCapGbPerMonth
      }
      scanResultsEventGridTopicResourceId: resultTopic.id
    }
    sensitiveDataDiscovery: {
      isEnabled: false
    }
  }
  dependsOn: [
    resultSubscription
  ]
}

output scannerStorageAccountId string = quarantineStorage.id
output scannerStorageAccountName string = quarantineStorage.name
output quarantineContainerName string = quarantineContainer.name
output scanResultTopicId string = resultTopic.id
output scanResultsQueueId string = scanResultsQueue.id
output scanResultSubscriptionId string = resultSubscription.id
output defenderSettingId string = defenderScanner.id
