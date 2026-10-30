param location string = resourceGroup().location
param environmentId string
param identityId string
param registryServer string
param imageDigest string
param managedIdentityClientId string
param postgresHost string
param postgresDatabase string
param postgresUser string
param postgresSslMode string
param reconcileScriptBase64 string

resource reconcileJob 'Microsoft.App/jobs@2024-03-01' = {
  name: 'salcapa-candidate-reconcile-b48224'
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
          name: 'salcapa-candidate-reconcile'
          image: imageDigest
          command: [ 'python', '-c' ]
          args: [
            'import base64;exec(compile(base64.b64decode("${reconcileScriptBase64}"),"<knowledge-candidate-reconcile>","exec"))'
          ]
          env: [
            { name: 'AZURE_CLIENT_ID', value: managedIdentityClientId }
            { name: 'SALUS_OIDC_MANAGED_IDENTITY_CLIENT_ID', value: managedIdentityClientId }
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
