param location string = resourceGroup().location
param environmentId string
param identityId string
param registryServer string
param imageDigest string
param tenantId string
param applicationClientId string
param managedIdentityClientId string
param driveId string
param folderItemId string
param acceptanceScriptBase64 string

resource acceptanceJob 'Microsoft.App/jobs@2024-03-01' = {
  name: 'salcapa-m365-acceptance-b48224'
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
      replicaTimeout: 600
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
          name: 'salcapa-m365-acceptance'
          image: imageDigest
          command: [
            'python'
            '-c'
          ]
          args: [
            'import base64;exec(compile(base64.b64decode("${acceptanceScriptBase64}"),"<m365-intake-live-acceptance>","exec"))'
          ]
          env: [
            { name: 'SALUS_OIDC_TENANT_ID', value: tenantId }
            { name: 'SALUS_OIDC_CLIENT_ID', value: applicationClientId }
            { name: 'SALUS_OIDC_MANAGED_IDENTITY_CLIENT_ID', value: managedIdentityClientId }
            { name: 'SALUS_M365_INTAKE_DRIVE_ID', value: driveId }
            { name: 'SALUS_M365_INTAKE_FOLDER_ITEM_ID', value: folderItemId }
            { name: 'SALUS_M365_INTAKE_MAX_FILE_BYTES', value: '26214400' }
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
