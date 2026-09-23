targetScope = 'resourceGroup'

@description('Short globally unique suffix used for Azure resource names.')
@minLength(4)
@maxLength(6)
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

@description('Immutable container image digest. Required only when provisionApplication is true.')
param containerImageDigest string = ''

@description('Create or update the SalCAPA Container App. Foundation-only provisioning leaves this false.')
param provisionApplication bool = false

@description('Microsoft Entra tenant ID used by SalCAPA.')
param entraTenantId string

@description('Client ID of the SalCAPA Microsoft Entra application registration used for interactive runtime sign-in. May be empty for foundation-only provisioning; deployment requires an exact UUID.')
param entraRuntimeClientId string = ''

@description('Microsoft 365 drive ID containing the dedicated generated-report folder. Empty for foundation-only provisioning.')
param m365ReportDriveId string = ''

@description('Microsoft 365 folder item ID for generated SalCAPA reports. Empty for foundation-only provisioning.')
param m365ReportFolderItemId string = ''

@description('Immutable object ID of the approved PostgreSQL Microsoft Entra administrator.')
param postgresAdminObjectId string

@description('Display name of the approved PostgreSQL Microsoft Entra administrator.')
param postgresAdminPrincipalName string

@allowed([
  'Group'
  'User'
])
param postgresAdminPrincipalType string = 'Group'

@description('Object ID of the GitHub OIDC deployment principal. It receives AcrPush only on the SalCAPA registry.')
param deploymentPrincipalObjectId string

@allowed([
  'MD-APPROVAL-AZURE-LEAN-20260904'
])
param approvalRecord string = 'MD-APPROVAL-AZURE-LEAN-20260904'

@minValue(30)
@maxValue(30)
param monthlyCostCeilingUsd int = 30

@description('Monthly operational Azure Consumption budget. Fixed below the approved authorization ceiling.')
@minValue(25)
@maxValue(25)
param operationalBudgetUsd int = 25

@description('Exact governed source commit used to provision or update this environment.')
@minLength(40)
@maxLength(40)
param sourceCommit string

@description('Notification recipient for governed Azure budget alerts. Supplied from a protected GitHub variable.')
@minLength(3)
param budgetContactEmail string

@description('First day of the budget period. Defaults to the current UTC month.')
param budgetStartDate string = utcNow('yyyy-MM-01T00:00:00Z')

var stem = 'salcapa-${environmentName}-${uniqueSuffix}'
var evidenceContainerName = 'evidence'
var registryName = replace('${stem}acr', '-', '')
var databaseName = 'salcapa'
var postgresServerName = '${stem}-pg'
var workloadIdentityName = '${stem}-identity'
var runtimeRedirectUri = environmentName == 'dev' ? 'https://salcapa.salus.solutions/api/auth/oidc/callback' : 'https://${stem}.${containerAppsEnvironment.properties.defaultDomain}/api/auth/oidc/callback'
var commonTags = {
  system: 'SalCAPA'
  environment: environmentName
  approvalRecord: approvalRecord
  monthlyCostCeilingUsd: string(monthlyCostCeilingUsd)
  costArchitecture: 'lean-container-apps-consumption'
  sourceCommit: sourceCommit
}

resource operationalBudget 'Microsoft.Consumption/budgets@2023-11-01' = {
  name: '${stem}-monthly-budget'
  properties: {
    amount: operationalBudgetUsd
    category: 'Cost'
    timeGrain: 'Monthly'
    timePeriod: {
      startDate: budgetStartDate
    }
    notifications: {
      Actual80Percent: {
        enabled: true
        operator: 'GreaterThanOrEqualTo'
        threshold: 80
        thresholdType: 'Actual'
        contactEmails: [
          budgetContactEmail
        ]
      }
      Forecast100Percent: {
        enabled: true
        operator: 'GreaterThanOrEqualTo'
        threshold: 100
        thresholdType: 'Forecasted'
        contactEmails: [
          budgetContactEmail
        ]
      }
      Actual100Percent: {
        enabled: true
        operator: 'GreaterThanOrEqualTo'
        threshold: 100
        thresholdType: 'Actual'
        contactEmails: [
          budgetContactEmail
        ]
      }
    }
  }
}

resource virtualNetwork 'Microsoft.Network/virtualNetworks@2024-07-01' = {
  name: '${stem}-vnet'
  location: location
  tags: commonTags
  properties: {
    addressSpace: {
      addressPrefixes: [
        '10.42.0.0/16'
      ]
    }
  }
}

resource containerAppsSubnet 'Microsoft.Network/virtualNetworks/subnets@2024-07-01' = {
  parent: virtualNetwork
  name: 'container-apps'
  properties: {
    addressPrefix: '10.42.1.0/27'
    delegations: [
      {
        name: 'container-apps-delegation'
        properties: {
          serviceName: 'Microsoft.App/environments'
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
  tags: commonTags
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
  tags: commonTags
  sku: {
    name: 'Basic'
  }
  properties: {
    adminUserEnabled: false
    dataEndpointEnabled: false
    networkRuleBypassOptions: 'AzureServices'
    publicNetworkAccess: 'Enabled'
    zoneRedundancy: 'Disabled'
  }
}

resource deploymentRegistryPushRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(registry.id, deploymentPrincipalObjectId, 'acr-push')
  scope: registry
  properties: {
    principalId: deploymentPrincipalObjectId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '8311e382-0749-4cb8-b61a-304f252e45ec')
  }
}

resource workloadIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: workloadIdentityName
  location: location
  tags: commonTags
}

resource postgres 'Microsoft.DBforPostgreSQL/flexibleServers@2024-08-01' = {
  name: postgresServerName
  location: location
  tags: commonTags
  identity: {
    type: 'SystemAssigned'
  }
  sku: {
    name: 'Standard_B1ms'
    tier: 'Burstable'
  }
  properties: {
    authConfig: {
      activeDirectoryAuth: 'Enabled'
      passwordAuth: 'Disabled'
      tenantId: entraTenantId
    }
    availabilityZone: '1'
    backup: {
      backupRetentionDays: 14
      geoRedundantBackup: 'Disabled'
    }
    createMode: 'Default'
    highAvailability: {
      mode: 'Disabled'
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
      storageSizeGB: 32
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
  tags: commonTags
  properties: {
    retentionInDays: 30
    sku: {
      name: 'PerGB2018'
    }
    workspaceCapping: {
      dailyQuotaGb: json('0.1')
    }
  }
}

resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: '${stem}-appinsights'
  location: location
  tags: commonTags
  kind: 'web'
  properties: {
    Application_Type: 'web'
    SamplingPercentage: 5
    RetentionInDays: 30
    WorkspaceResourceId: logAnalytics.id
  }
}

resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: replace('${stem}storage', '-', '')
  location: location
  tags: commonTags
  sku: {
    name: 'Standard_LRS'
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
      days: 14
    }
    containerDeleteRetentionPolicy: {
      enabled: true
      days: 14
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
  tags: commonTags
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

resource containerAppsEnvironment 'Microsoft.App/managedEnvironments@2025-01-01' = {
  name: '${stem}-aca-env'
  location: location
  tags: commonTags
  properties: {
    appLogsConfiguration: {
      destination: 'azure-monitor'
    }
    vnetConfiguration: {
      infrastructureSubnetId: containerAppsSubnet.id
      internal: false
    }
    workloadProfiles: [
      {
        name: 'Consumption'
        workloadProfileType: 'Consumption'
      }
    ]
    zoneRedundant: false
  }
}

resource evidenceRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(evidenceContainer.id, workloadIdentity.id, 'blob-data-contributor')
  scope: evidenceContainer
  properties: {
    principalId: workloadIdentity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'ba92f5b4-2d11-453d-a403-e96b0029c9fe')
  }
}

resource vaultRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(keyVault.id, workloadIdentity.id, 'vault-secrets-user')
  scope: keyVault
  properties: {
    principalId: workloadIdentity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '4633458b-17de-408a-b874-0445c86b69e6')
  }
}

resource registryPullRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(registry.id, workloadIdentity.id, 'acr-pull')
  scope: registry
  properties: {
    principalId: workloadIdentity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7f951dda-4ed3-4680-a7ca-43fe172d538d')
  }
}

resource containerApp 'Microsoft.App/containerApps@2025-01-01' = if (provisionApplication) {
  name: stem
  location: location
  tags: commonTags
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${workloadIdentity.id}': {}
    }
  }
  properties: {
    managedEnvironmentId: containerAppsEnvironment.id
    workloadProfileName: 'Consumption'
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: true
        allowInsecure: false
        targetPort: 8000
        transport: 'auto'
      }
      registries: [
        {
          server: registry.properties.loginServer
          identity: workloadIdentity.id
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'salcapa'
          image: containerImageDigest
          resources: {
            cpu: json('0.25')
            memory: '0.5Gi'
          }
          env: [
            {
              name: 'SALUS_ENV'
              value: environmentName
            }
            {
              name: 'SALUS_AUTH_MODE'
              value: 'oidc'
            }
            {
              name: 'SALUS_OIDC_TENANT_ID'
              value: entraTenantId
            }
            {
              name: 'SALUS_OIDC_DISCOVERY_URL'
              value: 'https://login.microsoftonline.com/${entraTenantId}/v2.0/.well-known/openid-configuration'
            }
            {
              name: 'SALUS_OIDC_CLIENT_ID'
              value: entraRuntimeClientId
            }
            {
              name: 'SALUS_OIDC_CLIENT_AUTH_METHOD'
              value: 'managed_identity'
            }
            {
              name: 'SALUS_OIDC_MANAGED_IDENTITY_CLIENT_ID'
              value: workloadIdentity.properties.clientId
            }
            {
              name: 'AZURE_CLIENT_ID'
              value: workloadIdentity.properties.clientId
            }
            {
              name: 'SALUS_OIDC_REDIRECT_URI'
              value: runtimeRedirectUri
            }
            {
              name: 'SALUS_OIDC_PROVIDER_NAME'
              value: 'entra'
            }
            {
              name: 'SALUS_OIDC_AUTO_PROVISION'
              value: '0'
            }
            {
              name: 'SALUS_COOKIE_SECURE'
              value: '1'
            }
            {
              name: 'SALUS_ADVISOR_NOTIFICATION_MODE'
              value: 'graph'
            }
            {
              name: 'SALUS_ADVISOR_NOTIFICATION_FROM'
              value: 'protectionadvisor@salus.solutions'
            }
            {
              name: 'SALUS_ADVISOR_NOTIFICATION_TO'
              value: 'mduncan@salus.solutions'
            }
            {
              name: 'SALUS_ADVISOR_REQUIRE_EMAIL_VERIFICATION'
              value: '0'
            }
            {
              name: 'SALUS_M365_INTAKE_DRIVE_ID'
              value: 'b!nLoH4rpIs0Ko75C0IRSSqNFy_EdwB-BMgQS848yr84pGrXen1bnSR6zYkxtw-PFF'
            }
            {
              name: 'SALUS_M365_INTAKE_FOLDER_ITEM_ID'
              value: '01DBTAFUKSE2CSFDDEING2AAXOVQQEYNNL'
            }
            {
              name: 'SALUS_M365_INTAKE_MAX_FILE_BYTES'
              value: '104857600'
            }
            {
              name: 'SALUS_M365_KNOWLEDGE_DRIVE_ID'
              value: 'b!mn-UaUzJ6UOGBLc9xcQ2DYwuRoUBrB9KtakxYIYG5o1riGTeQsB8T4jy0ttFW_fN'
            }
            {
              name: 'SALUS_M365_KNOWLEDGE_FOLDER_ITEM_ID'
              value: '01WETF6P56Y2GOVW7725BZO354PWSELRRZ'
            }
            {
              name: 'SALUS_M365_PROCESSED_INTAKE_FOLDER_ITEM_ID'
              value: '01DBTAFULEFCM3ALTBFNHZVKGCHE7QGFJ4'
            }
            {
              name: 'SALUS_KNOWLEDGE_SCAN_INTERVAL_SECONDS'
              value: '60'
            }
            {
              name: 'SALUS_KNOWLEDGE_BACKGROUND_SCAN'
              value: '0'
            }
            {
              name: 'SALUS_M365_REPORT_DRIVE_ID'
              value: m365ReportDriveId
            }
            {
              name: 'SALUS_M365_REPORT_FOLDER_ITEM_ID'
              value: m365ReportFolderItemId
            }
            {
              name: 'SALUS_M365_ADVISOR_REPORT_FOLDER_ITEM_ID'
              value: m365ReportFolderItemId
            }
            {
              name: 'SALUS_ADVISOR_DOCX_TEMPLATE_PATH'
              value: '/app/Protection Advisor Report Template.docx'
            }
            {
              name: 'SALUS_ADVISOR_REPORT_OUTPUT_DIR'
              value: '/app/data/advisor-reports'
            }
            {
              name: 'SALUS_M365_REPORT_MAX_FILE_BYTES'
              value: '26214400'
            }
            {
              name: 'SALUS_M365_REPORT_RETRIES'
              value: '3'
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
              value: workloadIdentity.name
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
          ]
        }
      ]
      scale: {
        minReplicas: 0
        maxReplicas: 1
        rules: [
          {
            name: 'http'
            http: {
              metadata: {
                concurrentRequests: '25'
              }
            }
          }
        ]
      }
    }
  }
  dependsOn: [
    evidenceRole
    vaultRole
    registryPullRole
  ]
}


resource knowledgeScanJob 'Microsoft.App/jobs@2024-03-01' = if (provisionApplication) {
  name: '${stem}-knowledge-scan'
  location: location
  tags: commonTags
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${workloadIdentity.id}': {}
    }
  }
  properties: {
    environmentId: containerAppsEnvironment.id
    configuration: {
      triggerType: 'Schedule'
      replicaTimeout: 300
      replicaRetryLimit: 0
      scheduleTriggerConfig: {
        cronExpression: '*/5 * * * *'
        parallelism: 1
        replicaCompletionCount: 1
      }
      registries: [
        {
          server: registry.properties.loginServer
          identity: workloadIdentity.id
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'salcapa-knowledge-scan'
          image: containerImageDigest
          command: [
            'python'
            'tools/salcapa_knowledge_scan_once.py'
          ]
          resources: {
            cpu: json('0.25')
            memory: '0.5Gi'
          }
          env: [
            { name: 'SALUS_ENV', value: environmentName }
            { name: 'AZURE_CLIENT_ID', value: workloadIdentity.properties.clientId }
            { name: 'SALUS_OIDC_TENANT_ID', value: entraTenantId }
            { name: 'SALUS_OIDC_CLIENT_ID', value: entraRuntimeClientId }
            { name: 'SALUS_OIDC_MANAGED_IDENTITY_CLIENT_ID', value: workloadIdentity.properties.clientId }
            { name: 'SALUS_M365_INTAKE_DRIVE_ID', value: 'b!nLoH4rpIs0Ko75C0IRSSqNFy_EdwB-BMgQS848yr84pGrXen1bnSR6zYkxtw-PFF' }
            { name: 'SALUS_M365_INTAKE_FOLDER_ITEM_ID', value: '01DBTAFUKSE2CSFDDEING2AAXOVQQEYNNL' }
            { name: 'SALUS_M365_INTAKE_MAX_FILE_BYTES', value: '104857600' }
            { name: 'SALUS_M365_KNOWLEDGE_DRIVE_ID', value: 'b!mn-UaUzJ6UOGBLc9xcQ2DYwuRoUBrB9KtakxYIYG5o1riGTeQsB8T4jy0ttFW_fN' }
            { name: 'SALUS_M365_KNOWLEDGE_FOLDER_ITEM_ID', value: '01WETF6P56Y2GOVW7725BZO354PWSELRRZ' }
            { name: 'SALUS_M365_PROCESSED_INTAKE_FOLDER_ITEM_ID', value: '01DBTAFULEFCM3ALTBFNHZVKGCHE7QGFJ4' }
            { name: 'SALUS_DB_BACKEND', value: 'postgres' }
            { name: 'SALUS_POSTGRES_AUTH', value: 'entra' }
            { name: 'SALUS_POSTGRES_HOST', value: postgres.properties.fullyQualifiedDomainName }
            { name: 'SALUS_POSTGRES_DATABASE', value: databaseName }
            { name: 'SALUS_POSTGRES_USER', value: workloadIdentity.name }
            { name: 'SALUS_POSTGRES_SSLMODE', value: 'require' }
            { name: 'SALUS_MANAGED_DB_TARGET', value: 'azure_postgresql' }
            { name: 'SALUS_SECRET_BACKEND', value: 'azure_keyvault' }
            { name: 'SALUS_KEY_VAULT_URL', value: keyVault.properties.vaultUri }
            { name: 'SALUS_STORAGE_BACKEND', value: 'azure' }
            { name: 'SALUS_AZURE_STORAGE_ACCOUNT_URL', value: storage.properties.primaryEndpoints.blob }
            { name: 'SALUS_AZURE_STORAGE_CONTAINER', value: evidenceContainerName }
            { name: 'SALUS_TELEMETRY_BACKEND', value: 'azure_monitor' }
            { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', value: appInsights.properties.ConnectionString }
          ]
        }
      ]
    }
  }
  dependsOn: [
    evidenceRole
    vaultRole
    registryPullRole
  ]
}

output applicationName string = stem
output containerAppsEnvironmentName string = containerAppsEnvironment.name
output managedIdentityName string = workloadIdentity.name
output managedIdentityPrincipalId string = workloadIdentity.properties.principalId
output managedIdentityClientId string = workloadIdentity.properties.clientId
output federatedCredentialIssuer string = 'https://login.microsoftonline.com/${entraTenantId}/v2.0'
output federatedCredentialSubject string = workloadIdentity.properties.principalId
output federatedCredentialAudience string = 'api://AzureADTokenExchange'
output runtimeRedirectUri string = runtimeRedirectUri
output entraRuntimeClientId string = entraRuntimeClientId
output storageAccountName string = storage.name
output keyVaultName string = keyVault.name
output registryName string = registry.name
output registryLoginServer string = registry.properties.loginServer
output postgresServerName string = postgres.name
output postgresHostName string = postgres.properties.fullyQualifiedDomainName
output postgresDatabaseName string = salcapaDatabase.name
output monthlyCostCeilingUsd int = monthlyCostCeilingUsd
output operationalBudgetUsd int = operationalBudgetUsd
output operationalBudgetName string = operationalBudget.name
output approvalRecord string = approvalRecord
