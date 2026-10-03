targetScope = 'resourceGroup'

// Candidate only. Deploy through a separately reviewed protected workflow and
// exact Azure what-if. This job has no ingress, schedule, worker reader identity,
// or public Member switch. Its source runs only on fictional fixture records.
@allowed([
  'dev'
])
param environmentName string

@minLength(4)
@maxLength(6)
param uniqueSuffix string

@allowed([
  'eastus2'
  'southcentralus'
])
param location string

@description('Immutable reviewed application image by sha256 digest, never a mutable tag.')
@minLength(80)
param imageDigest string

@description('Exact reviewed source commit that produced the image.')
@minLength(40)
@maxLength(40)
param sourceCommit string

@description('Recorded exact-source, cost, identity and protected-job approval.')
@minLength(12)
param approvalRecord string

var stem = 'salcapa-${environmentName}-${uniqueSuffix}'
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

resource quarantineStorage 'Microsoft.Storage/storageAccounts@2023-05-01' existing = {
  name: replace('${stem}scan', '-', '')
}

resource postgres 'Microsoft.DBforPostgreSQL/flexibleServers@2024-08-01' existing = {
  name: '${stem}-pg'
}

resource acceptanceJob 'Microsoft.App/jobs@2025-01-01' = {
  name: '${stem}-scan-acceptance'
  location: location
  tags: {
    system: 'SalCAPA'
    environment: environmentName
    purpose: 'fictional-only-private-scanner-acceptance'
    approvalRecord: approvalRecord
    sourceCommit: sourceCommit
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
          name: 'fictional-scan-acceptance'
          image: imageDigest
          command: [
            'python'
            '-m'
            'tools.private_scanner_acceptance'
            '--execute'
          ]
          resources: {
            cpu: json('0.25')
            memory: '0.5Gi'
          }
          env: [
            { name: 'SALUS_ACCEPTANCE_PRIVATE_JOB', value: '1' }
            { name: 'SALUS_ACCEPTANCE_JOB_NAME', value: '${stem}-scan-acceptance' }
            { name: 'SALUS_ENV', value: environmentName }
            { name: 'SALUS_AUTH_MODE', value: 'session' }
            { name: 'SALUS_PACKAGE_COMMERCIAL_WORKFLOW_ENABLED', value: '1' }
            { name: 'SALUS_PACKAGE_SCAN_MODE', value: 'defender' }
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
            { name: 'SALUS_SCAN_QUARANTINE_URL', value: quarantineStorage.properties.primaryEndpoints.blob }
            { name: 'SALUS_ACCEPTANCE_EXPECTED_QUARANTINE_URL', value: quarantineStorage.properties.primaryEndpoints.blob }
            { name: 'AZURE_CLIENT_ID', value: runtimeIdentity.properties.clientId }
          ]
        }
      ]
    }
  }
}

output acceptanceJobId string = acceptanceJob.id

