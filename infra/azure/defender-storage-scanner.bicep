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

// Defender requires a same-region Event Grid topic reachable on public IPs.
// A governed subscription and authenticated receiver must be installed before
// any Protected Member upload is sent to this account.
resource resultTopic 'Microsoft.EventGrid/topics@2022-06-15' = {
  name: '${stem}-scan-results'
  location: location
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
}

output scannerStorageAccountId string = quarantineStorage.id
output scannerStorageAccountName string = quarantineStorage.name
output quarantineContainerName string = quarantineContainer.name
output scanResultTopicId string = resultTopic.id
output defenderSettingId string = defenderScanner.id
