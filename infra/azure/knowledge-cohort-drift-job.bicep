param location string = resourceGroup().location
param environmentId string
param identityId string
param registryServer string
param imageDigest string
param managedIdentityClientId string
param tenantId string
param applicationClientId string
param driveId string
param folderItemId string
param postgresHost string
param postgresDatabase string
param postgresUser string
param postgresSslMode string
param acceptanceScriptBase64 string
param phaseRunId string
param phaseScriptSha256 string
param supportScriptBase64 string

resource acceptanceJob 'Microsoft.App/jobs@2024-03-01' = {
  name: 'salcapa-cohort-drift-b48224'
  location: location
  tags: {
    salusOperation: 'knowledge-cohort-drift'
    salusTaskKey: 'salus-cohort-drift-readonly-20261115'
  }
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${identityId}': {}
    }
  }
  properties: {
    environmentId: environmentId
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
          server: registryServer
          identity: identityId
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'salcapa-cohort-drift'
          image: imageDigest
          command: [
            'python'
            '-c'
          ]
          args: [
            'import base64,sys,types;m=types.ModuleType("salus_postsearch_support");exec(compile(base64.b64decode("${supportScriptBase64}"),"<pinned-read-support>","exec"),m.__dict__);sys.modules[m.__name__]=m;exec(compile(base64.b64decode("${acceptanceScriptBase64}"),"<knowledge-ledger-live-acceptance>","exec"))'
          ]
          env: [
            { name: 'SALUS_POSTSEARCH_RUN_ID', value: phaseRunId }
            { name: 'SALUS_POSTSEARCH_SCRIPT_SHA256', value: phaseScriptSha256 }
            { name: 'AZURE_CLIENT_ID', value: managedIdentityClientId }
            { name: 'SALUS_OIDC_MANAGED_IDENTITY_CLIENT_ID', value: managedIdentityClientId }
            { name: 'SALUS_OIDC_TENANT_ID', value: tenantId }
            { name: 'SALUS_OIDC_CLIENT_ID', value: applicationClientId }
            { name: 'SALUS_M365_INTAKE_DRIVE_ID', value: driveId }
            { name: 'SALUS_M365_INTAKE_FOLDER_ITEM_ID', value: folderItemId }
            { name: 'SALUS_M365_INTAKE_MAX_FILE_BYTES', value: '104857600' }
            { name: 'SALUS_DB_BACKEND', value: 'postgres' }
            { name: 'SALUS_POSTGRES_AUTH', value: 'entra' }
            { name: 'SALUS_POSTGRES_HOST', value: postgresHost }
            { name: 'SALUS_POSTGRES_DATABASE', value: postgresDatabase }
            { name: 'SALUS_POSTGRES_USER', value: postgresUser }
            { name: 'SALUS_POSTGRES_SSLMODE', value: postgresSslMode }
          ]
          resources: {
            cpu: json('0.25')
            memory: '0.5Gi'
          }
        }
      ]
    }
  }
}
