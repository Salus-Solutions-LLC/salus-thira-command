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

@description('Immutable governed application image digest containing the scan worker; required before scanner activation.')
@minLength(80)
param imageDigest string

@description('Recorded scanner approval and updated spend authority.')
param approvalRecord string

var stem = 'salcapa-${environmentName}-${uniqueSuffix}'
var accountName = replace('${stem}-scan', '-', '')
var registryName = replace('${stem}acr', '-', '')

resource environment 'Microsoft.App/managedEnvironments@2025-01-01' existing = {
  name: '${stem}-aca-env'
}

resource registry 'Microsoft.ContainerRegistry/registries@2023-07-01' existing = {
  name: registryName
}

resource runtimeIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' existing = {
  name: '${stem}-identity'
}

resource evidenceStorage 'Microsoft.Storage/storageAccounts@2023-05-01' existing = {
  name: replace('${stem}storage', '-', '')
}

resource postgres 'Microsoft.DBforPostgreSQL/flexibleServers@2024-08-01' existing = {
  name: '${stem}-pg'
}

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

resource workerIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: '${stem}-scan-worker'
  location: location
  tags: {
    system: 'SalCAPA'
    environment: environmentName
    purpose: 'quarantine-read-and-result-processing'
    approvalRecord: approvalRecord
    sourceCommit: sourceCommit
  }
}

// The web identity may create originals, but must not read or delete them.
// Put Blob needs the Blob write data action for create/overwrite; application
// code additionally uses an unguessable name and overwrite=false.
resource quarantineCreateRole 'Microsoft.Authorization/roleDefinitions@2022-04-01' = {
  name: guid(resourceGroup().id, stem, 'quarantine-create-only')
  properties: {
    roleName: '${stem} quarantine create only'
    description: 'Create quarantined upload blobs; no read, list, or delete permission.'
    type: 'CustomRole'
    assignableScopes: [resourceGroup().id]
    permissions: [
      {
        actions: []
        notActions: []
        dataActions: [
          'Microsoft.Storage/storageAccounts/blobServices/containers/blobs/write'
        ]
        notDataActions: []
      }
    ]
  }
}

// Azure returns a subscription-root ID for this resource-group-assignable
// custom role. Use that canonical ID in role assignments and outputs.
var quarantineCreateRoleCanonicalId = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', quarantineCreateRole.name)

// The worker-only identity reads named originals and processes results.
// The runtime identity is attached separately for DB/evidence and image pull.
var blobReader = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '2a2b9908-6ea1-4ae2-8e65-a410df84e7d1')
var queueProcessor = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '8a0f0c08-91a1-4084-bc3d-661d67233fed')

resource runtimeQuarantineWriter 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(quarantineContainer.id, runtimeIdentity.id, quarantineCreateRoleCanonicalId)
  scope: quarantineContainer
  properties: {
    principalId: runtimeIdentity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: quarantineCreateRoleCanonicalId
  }
}

resource workerQuarantineReader 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(quarantineContainer.id, workerIdentity.id, blobReader)
  scope: quarantineContainer
  properties: {
    principalId: workerIdentity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: blobReader
  }
}

resource workerQueueProcessor 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(scanResultsQueue.id, workerIdentity.id, queueProcessor)
  scope: scanResultsQueue
  properties: {
    principalId: workerIdentity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: queueProcessor
  }
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

resource scanWorkerJob 'Microsoft.App/jobs@2025-01-01' = {
  name: '${stem}-scan-worker'
  location: location
  tags: {
    system: 'SalCAPA'
    environment: environmentName
    purpose: 'bounded-defender-result-processor'
    approvalRecord: approvalRecord
    sourceCommit: sourceCommit
  }
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${runtimeIdentity.id}': {}
      '${workerIdentity.id}': {}
    }
  }
  properties: {
    environmentId: environment.id
    workloadProfileName: 'Consumption'
    configuration: {
      triggerType: 'Schedule'
      replicaTimeout: 60
      replicaRetryLimit: 0
      scheduleTriggerConfig: {
        cronExpression: '*/5 * * * *'
        parallelism: 1
        replicaCompletionCount: 1
      }
      registries: [
        {
          server: registry.properties.loginServer
          identity: runtimeIdentity.id
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'scan-results'
          image: imageDigest
          command: ['python', '-m', 'salus_scan_worker']
          resources: {
            cpu: json('0.25')
            memory: '0.5Gi'
          }
          env: [
            { name: 'SALUS_ENV', value: environmentName }
            { name: 'SALUS_AUTH_MODE', value: 'oidc' }
            { name: 'SALUS_OIDC_CLIENT_AUTH_METHOD', value: 'managed_identity' }
            { name: 'SALUS_SEED_DEMO', value: '0' }
            { name: 'SALUS_DB_BACKEND', value: 'postgres' }
            { name: 'SALUS_POSTGRES_AUTH', value: 'managed_identity' }
            { name: 'SALUS_POSTGRES_HOST', value: postgres.properties.fullyQualifiedDomainName }
            { name: 'SALUS_POSTGRES_DATABASE', value: 'salcapa' }
            { name: 'SALUS_POSTGRES_USER', value: runtimeIdentity.name }
            { name: 'SALUS_POSTGRES_SSLMODE', value: 'require' }
            { name: 'SALUS_STORAGE_BACKEND', value: 'azure' }
            { name: 'SALUS_AZURE_STORAGE_ACCOUNT_URL', value: evidenceStorage.properties.primaryEndpoints.blob }
            { name: 'SALUS_AZURE_STORAGE_CONTAINER', value: 'evidence' }
            { name: 'SALUS_PACKAGE_SCAN_MODE', value: 'defender' }
            { name: 'SALUS_SCAN_QUARANTINE_URL', value: quarantineStorage.properties.primaryEndpoints.blob }
            { name: 'SALUS_SCAN_RESULTS_QUEUE_URL', value: '${quarantineStorage.properties.primaryEndpoints.queue}scan-results' }
            { name: 'SALUS_SCAN_RESULT_TOPIC_ID', value: resultTopic.id }
            { name: 'SALUS_SCAN_MANAGED_IDENTITY_CLIENT_ID', value: workerIdentity.properties.clientId }
            { name: 'AZURE_CLIENT_ID', value: runtimeIdentity.properties.clientId }
          ]
        }
      ]
    }
  }
  dependsOn: [
    runtimeQuarantineWriter
    workerQuarantineReader
    workerQueueProcessor
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
    scanWorkerJob
  ]
}

output scannerStorageAccountId string = quarantineStorage.id
output scannerStorageAccountName string = quarantineStorage.name
output quarantineContainerName string = quarantineContainer.name
output scanResultTopicId string = resultTopic.id
output scanResultsQueueId string = scanResultsQueue.id
output scanResultSubscriptionId string = resultSubscription.id
output scanWorkerIdentityId string = workerIdentity.id
output scanWorkerJobId string = scanWorkerJob.id
output quarantineCreateRoleId string = quarantineCreateRoleCanonicalId
output defenderSettingId string = defenderScanner.id
