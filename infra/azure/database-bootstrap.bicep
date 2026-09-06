targetScope = 'resourceGroup'

param location string = 'southcentralus'
param environmentName string = 'dev'
param uniqueSuffix string
param imageDigest string
param sourceCommit string
param approvalRecord string
param entraTenantId string
param tenantName string
param tenantSlug string
param initialUsersJson string

var stem = 'salcapa-${environmentName}-${uniqueSuffix}'
var registryName = replace('${stem}acr', '-', '')
var runtimeIdentityName = '${stem}-identity'
var bootstrapIdentityName = '${stem}-db-bootstrap'
var jobName = '${stem}-db-bootstrap'

resource postgres 'Microsoft.DBforPostgreSQL/flexibleServers@2024-08-01' existing = {
  name: '${stem}-pg'
}

resource registry 'Microsoft.ContainerRegistry/registries@2023-07-01' existing = {
  name: registryName
}

resource environment 'Microsoft.App/managedEnvironments@2025-01-01' existing = {
  name: '${stem}-aca-env'
}

resource runtimeIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' existing = {
  name: runtimeIdentityName
}

resource bootstrapIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: bootstrapIdentityName
  location: location
  tags: {
    system: 'SalCAPA'
    environment: environmentName
    purpose: 'transient-database-bootstrap'
    approvalRecord: approvalRecord
    sourceCommit: sourceCommit
  }
}

resource bootstrapJob 'Microsoft.App/jobs@2025-01-01' = {
  name: jobName
  location: location
  tags: {
    system: 'SalCAPA'
    environment: environmentName
    purpose: 'transient-database-bootstrap'
    approvalRecord: approvalRecord
    sourceCommit: sourceCommit
  }
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${runtimeIdentity.id}': {}
      '${bootstrapIdentity.id}': {}
    }
  }
  properties: {
    environmentId: environment.id
    workloadProfileName: 'Consumption'
    configuration: {
      triggerType: 'Manual'
      replicaTimeout: 1200
      replicaRetryLimit: 0
      manualTriggerConfig: {
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
          name: 'bootstrap'
          image: imageDigest
          command: [
            'python'
          ]
          args: [
            '-m'
            'tools.azure_database_bootstrap'
          ]
          resources: {
            cpu: json('0.25')
            memory: '0.5Gi'
          }
          env: [
            { name: 'SALUS_POSTGRES_HOST', value: postgres.properties.fullyQualifiedDomainName }
            { name: 'SALUS_POSTGRES_DATABASE', value: 'salcapa' }
            { name: 'SALUS_POSTGRES_USER', value: runtimeIdentity.name }
            { name: 'SALUS_RUNTIME_IDENTITY_CLIENT_ID', value: runtimeIdentity.properties.clientId }
            { name: 'SALUS_RUNTIME_IDENTITY_OBJECT_ID', value: runtimeIdentity.properties.principalId }
            { name: 'SALUS_BOOTSTRAP_IDENTITY_NAME', value: bootstrapIdentity.name }
            { name: 'SALUS_BOOTSTRAP_IDENTITY_CLIENT_ID', value: bootstrapIdentity.properties.clientId }
            { name: 'SALUS_BOOTSTRAP_TENANT_NAME', value: tenantName }
            { name: 'SALUS_BOOTSTRAP_TENANT_SLUG', value: tenantSlug }
            { name: 'SALUS_BOOTSTRAP_INITIAL_USERS_JSON', value: initialUsersJson }
          ]
        }
      ]
    }
  }
}

output bootstrapIdentityName string = bootstrapIdentity.name
output bootstrapIdentityObjectId string = bootstrapIdentity.properties.principalId
output bootstrapJobName string = bootstrapJob.name
output runtimeIdentityName string = runtimeIdentity.name
output runtimeIdentityObjectId string = runtimeIdentity.properties.principalId
