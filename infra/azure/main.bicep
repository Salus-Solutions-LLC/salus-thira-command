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

@description('Immutable object ID of the approved PostgreSQL Microsoft Entra administrator.')
param postgresAdminObjectId string

@description('Display name of the approved PostgreSQL Microsoft Entra administrator.')
param postgresAdminPrincipalName string

@allowed([
  'Group'
  'User'
])
param postgresAdminPrincipalType string = 'Group'

var stem = 'salcapa-${environmentName}-${uniqueSuffix}'
var evidenceContainerName = 'evidence'
var registryName = replace('${stem}acr', '-', '')
var databaseName = 'salcapa'
var postgresServerName = '${stem}-pg'

resource virtualNetwork 'Microsoft.Network/virtualNetworks@2024-07-01' = {
  name: '${stem}-vnet'
  location: location
  properties: {
    addressSpace: {
      addressPrefixes: [
        '10.42.0.0/16'
      ]
    }
  }
}

resource appSubnet 'Microsoft.Network/virtualNetworks/subnets@2024-07-01' = {
  parent: virtualNetwork
  name: 'app-integration'
  properties: {
    addressPrefix: '10.42.1.0/24'
    delegations: [
      {
        name: 'web-app-delegation'
        properties: {
          serviceName: 'Microsoft.Web/serverFarms'
        }
      }
    ]
  }
}

resource postgresSubnet 'Microsoft.Network/virtualNetworks/subnets@2024-07-01' = {
  parent: virtualNetwork
  name: 'postgresql'
  properties: {
    addressPrefix: '10.42.2.0/24'
    delegations: [
      {
        name: 'postgres-delegation'
        properties: {
          serviceName: 'Microsoft.DBforPostgreSQL/flexibleServers'
        }
      }
    ]
  }
}

resource postgresPrivateDns 'Microsoft.Network/privateDnsZones@2024-06-01' = {
  name: 'privatelink.postgres.database.azure.com'
  location: 'global'
}

resource postgresPrivateDnsLink 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2024-06-01' = {
  parent: postgresPrivateDns
  name: '${stem}-postgres-link'
  location: 'global'
  properties: {
    registrationEnabled: false
    virtualNetwork: {
      id: virtualNetwork.id
    }
  }
}

resource registry 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: registryName
  location: location
  sku: {
    name: environmentName == 'prod' ? 'Standard' : 'Basic'
  }
  properties: {
    adminUserEnabled: false
    anonymousPullEnabled: false
    dataEndpointEnabled: false
    networkRuleBypassOptions: 'AzureServices'
    publicNetworkAccess: 'Enabled'
    zoneRedundancy: 'Disabled'
  }
}

resource postgres 'Microsoft.DBforPostgreSQL/flexibleServers@2024-08-01' = {
  name: postgresServerName
  location: location
  identity: {
    type: 'SystemAssigned'
  }
  sku: {
    name: environmentName == 'prod' ? 'Standard_D2ds_v5' : 'Standard_B1ms'
    tier: environmentName == 'prod' ? 'GeneralPurpose' : 'Burstable'
  }
  properties: {
    authConfig: {
      activeDirectoryAuth: 'Enabled'
      passwordAuth: 'Disabled'
      tenantId: entraTenantId
    }
    availabilityZone: '1'
    backup: {
      backupRetentionDays: environmentName == 'prod' ? 35 : 14
      geoRedundantBackup: environmentName == 'prod' ? 'Enabled' : 'Disabled'
    }
    createMode: 'Default'
    highAvailability: {
      mode: environmentName == 'prod' ? 'ZoneRedundant' : 'Disabled'
      standbyAvailabilityZone: environmentName == 'prod' ? '2' : ''
    }
    maintenanceWindow: {
      customWindow: 'Enabled'
      dayOfWeek: 0
      startHour: 8
      startMinute: 0
    }
    network: {
      delegatedSubnetResourceId: postgresSubnet.id
      privateDnsZoneArmResourceId: postgresPrivateDns.id
      publicNetworkAccess: 'Disabled'
    }
    storage: {
      autoGrow: 'Enabled'
      storageSizeGB: environmentName == 'prod' ? 128 : 32
      type: 'Premium_LRS'
    }
    version: '16'
  }
  dependsOn: [
    postgresPrivateDnsLink
  ]
}

resource postgresAdministrator 'Microsoft.DBforPostgreSQL/flexibleServers/administrators@2024-08-01' = {
  parent: postgres
  name: postgresAdminObjectId
  properties: {
    principalName: postgresAdminPrincipalName
    principalType: postgresAdminPrincipalType
    tenantId: entraTenantId
  }
}

resource salcapaDatabase 'Microsoft.DBforPostgreSQL/flexibleServers/databases@2024-08-01' = {
  parent: postgres
  name: databaseName
  properties: {
    charset: 'UTF8'
    collation: 'en_US.utf8'
  }
}

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
    name: 'Standard_GRS'
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
    isVersioningEnabled: true
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
    capacity: environmentName == 'prod' ? 2 : 1
  }
  properties: {
    reserved: true
    zoneRedundant: false
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
    virtualNetworkSubnetId: appSubnet.id
    siteConfig: {
      acrUseManagedIdentityCreds: true
      alwaysOn: environmentName == 'prod'
      ftpsState: 'Disabled'
      http20Enabled: true
      minTlsVersion: '1.2'
      scmMinTlsVersion: '1.2'
      vnetRouteAllEnabled: true
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
          name: 'SALUS_POSTGRES_HOST'
          value: postgres.properties.fullyQualifiedDomainName
        }
        {
          name: 'SALUS_POSTGRES_DATABASE'
          value: databaseName
        }
        {
          name: 'SALUS_POSTGRES_USER'
          value: stem
        }
        {
          name: 'SALUS_POSTGRES_SSLMODE'
          value: 'require'
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
  name: guid(evidenceContainer.id, webApp.id, 'blob-data-contributor')
  scope: evidenceContainer
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

resource registryPullRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(registry.id, webApp.id, 'acr-pull')
  scope: registry
  properties: {
    principalId: webApp.identity.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7f951dda-4ed3-4680-a7ca-43fe172d538d')
  }
}

output applicationName string = webApp.name
output applicationHostName string = webApp.properties.defaultHostName
output managedIdentityPrincipalId string = webApp.identity.principalId
output storageAccountName string = storage.name
output keyVaultName string = keyVault.name
output registryName string = registry.name
output registryLoginServer string = registry.properties.loginServer
output postgresServerName string = postgres.name
output postgresHostName string = postgres.properties.fullyQualifiedDomainName
output postgresDatabaseName string = salcapaDatabase.name
