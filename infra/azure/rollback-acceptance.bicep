targetScope = 'resourceGroup'

param location string = 'southcentralus'
param environmentName string = 'dev'
param uniqueSuffix string
param imageDigest string
param sourceCommit string
param acceptedCommit string
param approvalRecord string
param restoredPostgresHost string
@allowed([
  'candidate'
  'accepted'
])
param phase string

var stem = 'salcapa-${environmentName}-${uniqueSuffix}'
var registryName = replace('${stem}acr', '-', '')
var runtimeIdentityName = '${stem}-identity'
var jobName = '${stem}-rollback-job'
var candidateArgs = [
  '-m'
  'salcapa_demo_fixtures'
  '--operation'
  'seed'
  '--authority'
  'ISSUE-124'
  '--acknowledgement'
  'FICTIONAL DEMONSTRATION DATA ONLY'
]
var acceptedArgs = [
  '-c'
  'import app; conn=app.db(); row=conn.execute("SELECT COUNT(*) AS c FROM assessments").fetchone(); assert int(row["c"]) >= 3; conn.close(); print("ACCEPTED_ROLLBACK_RUNTIME_DATABASE_COMPATIBLE")'
]
var jobArgs = phase == 'candidate' ? candidateArgs : acceptedArgs

resource registry 'Microsoft.ContainerRegistry/registries@2023-07-01' existing = {
  name: registryName
}

resource environment 'Microsoft.App/managedEnvironments@2025-01-01' existing = {
  name: '${stem}-aca-env'
}

resource runtimeIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' existing = {
  name: runtimeIdentityName
}

resource rollbackJob 'Microsoft.App/jobs@2025-01-01' = {
  name: jobName
  location: location
  tags: {
    system: 'SalCAPA'
    environment: environmentName
    purpose: 'temporary-rollback-acceptance'
    approvalRecord: approvalRecord
    acceptedCommit: acceptedCommit
    sourceCommit: sourceCommit
    rollbackPhase: phase
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
      replicaTimeout: 1800
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
          name: 'rollback-acceptance'
          image: imageDigest
          command: [
            'python'
          ]
          args: jobArgs
          resources: {
            cpu: json('0.25')
            memory: '0.5Gi'
          }
          env: [
            { name: 'AZURE_CLIENT_ID', value: runtimeIdentity.properties.clientId }
            { name: 'SALUS_DB_BACKEND', value: 'postgres' }
            { name: 'SALUS_POSTGRES_AUTH', value: 'managed_identity' }
            { name: 'SALUS_POSTGRES_HOST', value: restoredPostgresHost }
            { name: 'SALUS_POSTGRES_DATABASE', value: 'salcapa' }
            { name: 'SALUS_POSTGRES_USER', value: runtimeIdentity.name }
            { name: 'SALUS_POSTGRES_SSLMODE', value: 'require' }
            { name: 'SALUS_ENV', value: 'development' }
            { name: 'SALUS_AUTH_MODE', value: 'oidc' }
            { name: 'SALUS_OIDC_AUTO_PROVISION', value: '0' }
            { name: 'SALUS_SEED_DEMO', value: '0' }
            { name: 'SALUS_ALLOW_RESTORE', value: '0' }
            { name: 'SALUS_ALLOW_SQLITE_PRODUCTION', value: '0' }
            { name: 'SALUS_STORAGE_BACKEND', value: 'local' }
            { name: 'SALUS_SECRET_BACKEND', value: 'environment' }
            { name: 'SALUS_TELEMETRY_BACKEND', value: 'off' }
          ]
        }
      ]
    }
  }
}

output rollbackJobName string = rollbackJob.name
output runtimeIdentityName string = runtimeIdentity.name
output runtimeIdentityObjectId string = runtimeIdentity.properties.principalId
