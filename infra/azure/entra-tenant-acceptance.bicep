targetScope = 'resourceGroup'

param location string = 'southcentralus'
param environmentName string = 'dev'
param uniqueSuffix string
param imageDigest string
param sourceCommit string
param acceptedCommit string
param approvalRecord string
param entraTenantId string
param entraRuntimeClientId string
param entraRedirectUri string
@secure()
param acceptanceScriptBase64 string

var stem = 'salcapa-${environmentName}-${uniqueSuffix}'
var registryName = replace('${stem}acr', '-', '')
var runtimeIdentityName = '${stem}-identity'
var jobName = '${stem}-v311-entra'
var acceptanceCommand = 'import base64; exec(compile(base64.b64decode("${acceptanceScriptBase64}"), "azure_entra_tenant_acceptance.py", "exec"))'

resource registry 'Microsoft.ContainerRegistry/registries@2023-07-01' existing = {
  name: registryName
}

resource environment 'Microsoft.App/managedEnvironments@2025-01-01' existing = {
  name: '${stem}-aca-env'
}

resource runtimeIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' existing = {
  name: runtimeIdentityName
}

resource acceptanceJob 'Microsoft.App/jobs@2025-01-01' = {
  name: jobName
  location: location
  tags: {
    system: 'SalCAPA'
    environment: environmentName
    purpose: 'temporary-entra-tenant-isolation-acceptance'
    approvalRecord: approvalRecord
    acceptedCommit: acceptedCommit
    candidateCommit: sourceCommit
  }
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${runtimeIdentity.id}': {}
    }
  }
  properties: {
    environmentId: environment.id
    workloadProfileName: 'Consumption'
    configuration: {
      triggerType: 'Manual'
      replicaTimeout: 900
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
          name: 'entra-acceptance'
          image: imageDigest
          command: ['python']
          args: ['-c', acceptanceCommand]
          resources: {
            cpu: json('0.25')
            memory: '0.5Gi'
          }
          env: [
            { name: 'AZURE_CLIENT_ID', value: runtimeIdentity.properties.clientId }
            { name: 'SALCAPA_ACCEPTANCE_ROOT', value: '/app' }
            { name: 'SALUS_AUTH_MODE', value: 'oidc' }
            { name: 'SALUS_OIDC_TENANT_ID', value: entraTenantId }
            { name: 'SALUS_OIDC_DISCOVERY_URL', value: 'https://login.microsoftonline.com/${entraTenantId}/v2.0/.well-known/openid-configuration' }
            { name: 'SALUS_OIDC_CLIENT_ID', value: entraRuntimeClientId }
            { name: 'SALUS_OIDC_CLIENT_AUTH_METHOD', value: 'managed_identity' }
            { name: 'SALUS_OIDC_MANAGED_IDENTITY_CLIENT_ID', value: runtimeIdentity.properties.clientId }
            { name: 'SALUS_OIDC_REDIRECT_URI', value: entraRedirectUri }
            { name: 'SALUS_OIDC_PROVIDER_NAME', value: 'entra' }
            { name: 'SALUS_OIDC_AUTO_PROVISION', value: '0' }
            { name: 'SALUS_ALLOW_RESTORE', value: '0' }
            { name: 'SALUS_ALLOW_SQLITE_PRODUCTION', value: '0' }
            { name: 'SALUS_SECRET_BACKEND', value: 'environment' }
            { name: 'SALUS_TELEMETRY_BACKEND', value: 'off' }
          ]
        }
      ]
    }
  }
}

output acceptanceJobName string = acceptanceJob.name
output runtimeIdentityName string = runtimeIdentity.name
output runtimeIdentityObjectId string = runtimeIdentity.properties.principalId
