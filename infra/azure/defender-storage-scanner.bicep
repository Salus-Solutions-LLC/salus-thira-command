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

@description('Enable Event Grid delivery and billable Defender scanning only in stage two, after queue role propagation is verified.')
param activateScanner bool = false

@description('Exact reviewed source commit for the scanner installation.')
@minLength(40)
@maxLength(40)
param sourceCommit string

@description('Immutable governed application image digest containing the scan worker; required before scanner activation.')
@minLength(80)
param imageDigest string

@description('Recorded scanner approval and updated spend authority.')
param approvalRecord string

@secure()
@description('Approved Salus operations mailbox for scanner and inventory failure alerts; required for installation.')
param operationsAlertEmail string

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

resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2023-09-01' existing = {
  name: '${stem}-logs'
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

// Event Grid validates managed-identity delivery at the storage-account boundary.
// This account is dedicated to quarantine and currently contains only scan-results.
// Preserve the existing queue-scoped role while validating this provider requirement.
resource topicStorageAccountQueueSender 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(quarantineStorage.id, resultTopic.id, queueMessageSenderRole)
  scope: quarantineStorage
  properties: {
    roleDefinitionId: queueMessageSenderRole
    principalId: resultTopic.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

resource resultSubscription 'Microsoft.EventGrid/topics/eventSubscriptions@2022-06-15' = if (activateScanner) {
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
    topicStorageAccountQueueSender
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

// A separate daily reader catches a Blob staged before its ledger commit, as
// well as missing versions and retention/hold mismatches. It records exact
// exceptions in the server-side restricted ledger and logs counts only.
resource scanInventoryJob 'Microsoft.App/jobs@2025-01-01' = {
  name: '${stem}-scan-inv'
  location: location
  tags: {
    system: 'SalCAPA'
    environment: environmentName
    purpose: 'restricted-quarantine-version-reconciliation'
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
      replicaTimeout: 300
      replicaRetryLimit: 0
      scheduleTriggerConfig: {
        cronExpression: '0 2 * * *'
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
          name: 'scan-inventory'
          image: imageDigest
          command: ['python', '-m', 'salus_scan_inventory_worker']
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
            { name: 'SALUS_SCAN_MANAGED_IDENTITY_CLIENT_ID', value: workerIdentity.properties.clientId }
            { name: 'AZURE_CLIENT_ID', value: runtimeIdentity.properties.clientId }
          ]
        }
      ]
    }
  }
  dependsOn: [
    workerQuarantineReader
  ]
}

// This route deliberately has a real receiver. The existing development
// Smart Detection group has none, so a failed job there would not notify anyone.
resource scanAlertGroup 'Microsoft.Insights/actionGroups@2023-01-01' = {
  name: '${stem}-scan-alerts'
  location: 'global'
  tags: {
    system: 'SalCAPA'
    environment: environmentName
    purpose: 'quarantine-job-failure-notification'
    approvalRecord: approvalRecord
    sourceCommit: sourceCommit
  }
  properties: {
    enabled: true
    groupShortName: 'SalusScan'
    emailReceivers: [
      {
        name: 'salus-operations'
        emailAddress: operationsAlertEmail
        useCommonAlertSchema: true
      }
    ]
  }
}

// The first group returned GroupEmpty for a real controlled failure. Both groups
// later delivered duplicate Fired and Resolved emails to the same operations
// inbox. Retain this verified v2 route as the sole action on all four scanner
// alerts; the legacy group remains provisioned but unbound for rollback.
resource scanAlertGroupDeliveryRetry 'Microsoft.Insights/actionGroups@2023-01-01' = {
  name: '${stem}-scan-alerts-v2'
  location: 'global'
  tags: {
    system: 'SalCAPA'
    environment: environmentName
    purpose: 'quarantine-job-failure-notification-delivery-retry'
    approvalRecord: approvalRecord
    sourceCommit: sourceCommit
  }
  properties: {
    enabled: true
    groupShortName: 'SalusScan2'
    emailReceivers: [
      {
        name: 'salus-operations-v2'
        emailAddress: operationsAlertEmail
        useCommonAlertSchema: true
      }
    ]
  }
}

resource scanInventoryFailureAlert 'Microsoft.Insights/metricAlerts@2018-03-01' = {
  name: '${stem}-scan-inventory-failed'
  location: 'global'
  tags: {
    system: 'SalCAPA'
    environment: environmentName
    purpose: 'quarantine-inventory-failure'
    approvalRecord: approvalRecord
    sourceCommit: sourceCommit
  }
  properties: {
    description: 'A scheduled quarantine inventory execution failed or observed a restricted exception. Review the internal exception ledger; do not release held files.'
    severity: 2
    enabled: true
    scopes: [scanInventoryJob.id]
    targetResourceType: 'Microsoft.App/jobs'
    targetResourceRegion: location
    evaluationFrequency: 'PT5M'
    windowSize: 'PT5M'
    autoMitigate: true
    criteria: {
      'odata.type': 'Microsoft.Azure.Monitor.SingleResourceMultipleMetricCriteria'
      allOf: [
        {
          criterionType: 'StaticThresholdCriterion'
          name: 'FailedInventoryExecution'
          metricName: 'Executions'
          metricNamespace: 'Microsoft.App/jobs'
          timeAggregation: 'Total'
          operator: 'GreaterThan'
          threshold: 0
          skipMetricValidation: false
          dimensions: [
            {
              name: 'state'
              operator: 'Include'
              values: ['Failed']
            }
          ]
        }
      ]
    }
    actions: [
      {
        actionGroupId: scanAlertGroupDeliveryRetry.id
      }
    ]
  }
}

resource scanWorkerFailureAlert 'Microsoft.Insights/metricAlerts@2018-03-01' = {
  name: '${stem}-scan-result-worker-failed'
  location: 'global'
  tags: {
    system: 'SalCAPA'
    environment: environmentName
    purpose: 'scan-result-worker-failure'
    approvalRecord: approvalRecord
    sourceCommit: sourceCommit
  }
  properties: {
    description: 'A malware-scan result worker execution failed. Keep pending files on hold and investigate the result queue.'
    severity: 2
    enabled: true
    scopes: [scanWorkerJob.id]
    targetResourceType: 'Microsoft.App/jobs'
    targetResourceRegion: location
    evaluationFrequency: 'PT5M'
    windowSize: 'PT5M'
    autoMitigate: true
    criteria: {
      'odata.type': 'Microsoft.Azure.Monitor.SingleResourceMultipleMetricCriteria'
      allOf: [
        {
          criterionType: 'StaticThresholdCriterion'
          name: 'FailedScanResultExecution'
          metricName: 'Executions'
          metricNamespace: 'Microsoft.App/jobs'
          timeAggregation: 'Total'
          operator: 'GreaterThan'
          threshold: 0
          skipMetricValidation: false
          dimensions: [
            {
              name: 'state'
              operator: 'Include'
              values: ['Failed']
            }
          ]
        }
      ]
    }
    actions: [
      {
        actionGroupId: scanAlertGroupDeliveryRetry.id
      }
    ]
  }
}

// A failure alert alone cannot detect a schedule that never starts. The
// worker emits only a content-free completion marker after reconciliation;
// inventory already emits a bounded count summary. ACA logs use a generated
// EnvironmentName, so identify each job by either observed ContainerName form.
// Azure Monitor evaluates
// an empty period as zero without including Member details in the alert.
resource scanWorkerMissedRunAlert 'Microsoft.Insights/scheduledQueryRules@2023-12-01' = {
  name: '${stem}-scan-result-worker-missed'
  location: location
  tags: {
    system: 'SalCAPA'
    environment: environmentName
    purpose: 'scan-result-worker-missed-run'
    approvalRecord: approvalRecord
    sourceCommit: sourceCommit
  }
  properties: {
    displayName: 'SalCAPA scan-result worker missed run'
    description: 'No scan-result worker completion marker in 20 minutes. Keep pending originals on hold and check the job and log route.'
    enabled: true
    severity: 2
    evaluationFrequency: 'PT5M'
    windowSize: 'PT30M'
    autoMitigate: true
    scopes: [logAnalytics.id]
    criteria: {
      allOf: [
        {
          query: 'ContainerAppConsoleLogs | where TimeGenerated > ago(20m) | where ContainerName in (\'scan-results\', \'${stem}-scan-results\') | where tostring(parse_json(Log).scan_result_job) == \'completed\' | summarize CompletedRuns = count()'
          timeAggregation: 'Maximum'
          metricMeasureColumn: 'CompletedRuns'
          operator: 'LessThan'
          threshold: 1
          failingPeriods: {
            numberOfEvaluationPeriods: 1
            minFailingPeriodsToAlert: 1
          }
        }
      ]
    }
    actions: {
      actionGroups: [scanAlertGroupDeliveryRetry.id]
    }
  }
}

resource scanInventoryMissedRunAlert 'Microsoft.Insights/scheduledQueryRules@2023-12-01' = {
  name: '${stem}-scan-inventory-missed'
  location: location
  tags: {
    system: 'SalCAPA'
    environment: environmentName
    purpose: 'quarantine-inventory-missed-run'
    approvalRecord: approvalRecord
    sourceCommit: sourceCommit
  }
  properties: {
    displayName: 'SalCAPA quarantine inventory missed run'
    description: 'No daily quarantine-inventory summary in 27 hours. Keep originals on hold and check inventory and log delivery.'
    enabled: true
    severity: 2
    evaluationFrequency: 'PT1H'
    windowSize: 'PT48H'
    autoMitigate: true
    scopes: [logAnalytics.id]
    criteria: {
      allOf: [
        {
          query: 'ContainerAppConsoleLogs | where TimeGenerated > ago(27h) | where ContainerName in (\'scan-inventory\', \'${stem}-scan-inv\') | where isnotnull(parse_json(Log).exceptions_observed) | summarize CompletedRuns = count()'
          timeAggregation: 'Maximum'
          metricMeasureColumn: 'CompletedRuns'
          operator: 'LessThan'
          threshold: 1
          failingPeriods: {
            numberOfEvaluationPeriods: 1
            minFailingPeriodsToAlert: 1
          }
        }
      ]
    }
    actions: {
      actionGroups: [scanAlertGroupDeliveryRetry.id]
    }
  }
}

resource defenderScanner 'Microsoft.Security/defenderForStorageSettings@2025-06-01' = if (activateScanner) {
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
    scanInventoryJob
    scanInventoryFailureAlert
    scanWorkerFailureAlert
    scanWorkerMissedRunAlert
    scanInventoryMissedRunAlert
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
output scanInventoryJobId string = scanInventoryJob.id
output scanInventoryFailureAlertId string = scanInventoryFailureAlert.id
output scanWorkerFailureAlertId string = scanWorkerFailureAlert.id
output scanWorkerMissedRunAlertId string = scanWorkerMissedRunAlert.id
output scanInventoryMissedRunAlertId string = scanInventoryMissedRunAlert.id
output scanAlertGroupId string = scanAlertGroup.id
output quarantineCreateRoleId string = quarantineCreateRoleCanonicalId
output defenderSettingId string = activateScanner ? defenderScanner.id : ''

