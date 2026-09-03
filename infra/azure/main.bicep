targetScope = 'resourceGroup'

@description('Short globally unique suffix used for public Azure resource names.')
@minLength(4)
@maxLength(12)
param uniqueSuffix string

@allowed([
  'eastus2'
  'southcentralus'
])
param location string = 'southcentralus'

@allowed([
  'dev'
  'prod'
])
param environmentName string = 'dev'

@description('Container image digest. Tags such as latest are intentionally rejected by policy.')
param containerImageDigest string

@description('Microsoft Entra tenant ID used by the SalCAPA application.')
param entraTenantId string

var stem = 'salcapa-${environmentName}-${uniqueSuffix}'
var evidenceContainerName = 'evidence'

resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: '${stem}-logs'
  location: location
  properties: {
    retentionInDays: environmentName == 'prod' ? 90 : 30
  }
}

resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: '${stem}-appinsights'
  location: location
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logAnalytics.id
  }
}

resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: replace('${stem}storage', '-', '')
  location: location
  sku: {
    name: environmentName == 'prod' ? 'Standard_GRS' : 'Standard_LRS'
  }
  kind: 'StorageV2'
  properties: {
    allowBlobPublicAccess: false
    allowSharedKeyAccess: false
    defaultToOAuthAuthentication: true
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
  }
}

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' = {
  parent: storage
  name: 'default'
  properties: {
    deleteRetentionPolicy: {
      enabled: true
      days: environmentName == 'prod' ? 30 : 7
    }
    containerDeleteRetentionPolicy: {
      enabled: true
      days: environmentName == 'prod' ? 30 : 7
    }
  }
}

resource evidenceContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobService
  name: evidenceContainerName
  properties: {
    publicAccess: 'None'
  }
}

resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: '${stem}-kv'
  location: location
  properties: {
    tenantId: entraTenantId
    enableRbacAuthorization: true
    enablePurgeProtection: true
    enableSoftDelete: true
    softDeleteRetentionInDays: 90
    publicNetworkAccess: 'Enabled'
    sku: {
      family: 'A'
      name: 'standard'
    }
  }
}

resource appPlan 'Microsoft.Web/serverfarms@2023-12-01' = {
  name: '${stem}-plan'
  location: location
  kind: 'linux'
  sku: {
    name: environmentName == 'prod' ? 'P0v3' : 'B1'
  }
  properties: {
    reserved: true
  }
}

resource webApp 'Microsoft.Web/sites@2023-12-01' = {
  name: stem
  location: location
  kind: 'app,linux,container'
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    serverFarmId: appPlan.id
    httpsOnly: true
    clientAffinityEnabled: false
    siteConfig: {
      alwaysOn: environmentName == 'prod'
      ftpsState: 'Disabled'
      http20Enabled: true
      minimumTlsVersion: '1.2'
      linuxFxVersion: 'DOCKER|${containerImageDigest}'
      healthCheckPath: '/health/ready'
      appSettings: [
        {
          name: 'SALUS_ENV'
          value: environmentName
        }
        {
          name: 'SALUS_AUTH_MODE'
          value: 'oidc'
        }
        {
          name: 'SALUS_COOKIE_SECURE'
          value: '1'
        }
        {
          name: 'SALUS_ALLOW_RESTORE'
          value: '0'
        }
        {
          name: 'SALUS_SEED_DEMO'
          value: '0'
        }
        {
          name: 'SALUS_ALLOW_SQLITE_PRODUCTION'
          value: '0'
        }
        {
          name: 'SALUS_DB_BACKEND'
          value: 'postgres'
        }
        {
          name: 'SALUS_POSTGRES_AUTH'
          value: 'entra'
        }
        {
          name: 'SALUS_MANAGED_DB_TARGET'
          value: 'azure_postgresql'
        }
        {
          name: 'SALUS_SECRET_BACKEND'
          value: 'azure_keyvault'
        }
        {
          name: 'SALUS_KEY_VAULT_URL'
          value: keyVault.properties.vaultUri
        }
        {
          name: 'SALUS_STORAGE_BACKEND'
          value: 'azure'
        }
        {
          name: 'SALUS_AZURE_STORAGE_ACCOUNT_URL'
          value: storage.properties.primaryEndpoints.blob
        }
        {
          name: 'SALUS_AZURE_STORAGE_CONTAINER'
          value: evidenceContainerName
        }
        {
          name: 'SALUS_TELEMETRY_BACKEND'
          value: 'azure_monitor'
        }
        {
          name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
          value: appInsights.properties.ConnectionString
        }
        {
          name: 'WEBSITES_PORT'
          value: '8000'
        }
      ]
    }
  }
}

resource evidenceRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storage.id, webApp.id, 'blob-data-contributor')
  scope: storage
  properties: {
    principalId: webApp.identity.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'ba92f5b4-2d11-453d-a403-e96b0029c9fe')
  }
}

resource vaultRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(keyVault.id, webApp.id, 'vault-secrets-user')
  scope: keyVault
  properties: {
    principalId: webApp.identity.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '4633458b-17de-408a-b874-0445c86b69e6')
  }
}

output applicationName string = webApp.name
output applicationHostName string = webApp.properties.defaultHostName
output managedIdentityPrincipalId string = webApp.identity.principalId
output storageAccountName string = storage.name
output keyVaultName string = keyVault.name
