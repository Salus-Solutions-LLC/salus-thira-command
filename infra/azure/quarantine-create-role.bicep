targetScope = 'resourceGroup'

@description('Environment whose upload-quarantine role is prepared.')
@allowed([
  'dev'
  'prod'
])
param environmentName string

@description('Existing governed SalCAPA deployment suffix.')
@minLength(4)
@maxLength(6)
param uniqueSuffix string

var stem = 'salcapa-${environmentName}-${uniqueSuffix}'

// This cost-free preparatory role uses the same deterministic identity and
// definition as defender-storage-scanner.bicep. It grants no access until a
// later, separately reviewed container-scoped assignment is deployed.
resource quarantineCreateRole 'Microsoft.Authorization/roleDefinitions@2022-04-01' = {
  name: guid(resourceGroup().id, stem, 'quarantine-create-only')
  properties: {
    roleName: '${stem} quarantine create only'
    description: 'Create quarantined upload blobs; no read, list, or delete permission.'
    type: 'CustomRole'
    assignableScopes: [resourceGroup().id]
    permissions: [
      {
        actions: []
        notActions: []
        dataActions: [
          'Microsoft.Storage/storageAccounts/blobServices/containers/blobs/write'
        ]
        notDataActions: []
      }
    ]
  }
}

output quarantineCreateRoleId string = quarantineCreateRole.id
