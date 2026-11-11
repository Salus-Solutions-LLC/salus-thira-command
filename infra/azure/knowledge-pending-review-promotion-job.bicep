param location string = resourceGroup().location
param environmentId string
param identityId string
param registryServer string
param imageDigest string
param tenantId string
param applicationClientId string
param managedIdentityClientId string
param intakeDriveId string
param intakeFolderItemId string
param knowledgeDriveId string
param knowledgeFolderItemId string
param processedFolderItemId string
param postgresHost string
param postgresDatabase string
param postgresUser string
param postgresSslMode string
param promotionScriptBase64 string

resource promotionJob 'Microsoft.App/jobs@2024-03-01' = {
  name: 'salcapa-review-promote-b48224'
  location: location
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
      replicaTimeout: 3600
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
          name: 'salcapa-review-promote'
          image: imageDigest
          command: [ 'python', '-c' ]
          args: [
            'import base64;exec(compile(base64.b64decode("${promotionScriptBase64}"),"<knowledge-pending-review-promotion>","exec"))'
          ]
          env: [
            { name: 'AZURE_CLIENT_ID', value: managedIdentityClientId }
            { name: 'SALUS_OIDC_TENANT_ID', value: tenantId }
            { name: 'SALUS_OIDC_CLIENT_ID', value: applicationClientId }
            { name: 'SALUS_OIDC_MANAGED_IDENTITY_CLIENT_ID', value: managedIdentityClientId }
            { name: 'SALUS_M365_INTAKE_DRIVE_ID', value: intakeDriveId }
            { name: 'SALUS_M365_INTAKE_FOLDER_ITEM_ID', value: intakeFolderItemId }
            { name: 'SALUS_M365_INTAKE_MAX_FILE_BYTES', value: '104857600' }
            { name: 'SALUS_M365_KNOWLEDGE_DRIVE_ID', value: knowledgeDriveId }
            { name: 'SALUS_M365_KNOWLEDGE_FOLDER_ITEM_ID', value: knowledgeFolderItemId }
            { name: 'SALUS_M365_PROCESSED_INTAKE_FOLDER_ITEM_ID', value: processedFolderItemId }
            { name: 'SALUS_DB_BACKEND', value: 'postgres' }
            { name: 'SALUS_POSTGRES_AUTH', value: 'entra' }
            { name: 'SALUS_POSTGRES_HOST', value: postgresHost }
            { name: 'SALUS_POSTGRES_DATABASE', value: postgresDatabase }
            { name: 'SALUS_POSTGRES_USER', value: postgresUser }
            { name: 'SALUS_POSTGRES_SSLMODE', value: postgresSslMode }
          ]
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
        }
      ]
    }
  }
}
