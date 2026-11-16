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
param scriptsBase64 string
param payloadSha256 string
param phaseRunId string
param phaseScriptSha256 string

resource acceptanceJob 'Microsoft.App/jobs@2024-03-01' = {
  name: 'salcapa-outdrift-b48224'
  location: location
  tags: {
    salusOperation: 'knowledge-outside-cohort-drift'
    salusTaskKey: 'salus-outside-cohort-drift-reconciliation-20261116'
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
          name: 'salcapa-outdrift'
          image: imageDigest
          command: [
            'python'
            '-c'
          ]
          args: [
            'import base64,zlib,json,hashlib,types,sys;d=zlib.decompressobj();raw=d.decompress(base64.b64decode("${scriptsBase64}",validate=True),262145);assert len(raw)<=262144 and d.eof and not d.unconsumed_tail and not d.unused_data;assert hashlib.sha256(raw).hexdigest()=="${payloadSha256}";rows=json.loads(raw);names=["salus_postsearch_support","salus_baseline_support","salus_streamed_plan_support","salus_remediation_support","__main__"];assert [r["name"] for r in rows]==names;codes=[base64.b64decode(r["source"],validate=True) for r in rows];assert all(hashlib.sha256(c).hexdigest()==r["sha256"] for r,c in zip(rows,codes));modules={n:types.ModuleType(n) for n in names};sys.modules.update(modules);[exec(compile(c,"<pinned-recovery-module>","exec"),modules[n].__dict__) for n,c in zip(names,codes)]'
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
            cpu: json('0.5')
            memory: '1Gi'
          }
        }
      ]
    }
  }
}
