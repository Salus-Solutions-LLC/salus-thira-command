import os
import re
from pathlib import Path
from secret_provider import secret

class StorageError(RuntimeError):
    pass

class LocalStorage:
    backend='local'
    def __init__(self, root: str):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
    def _path(self, key: str) -> Path:
        if not isinstance(key,str) or not key or len(key)>1024 or '\\x00' in key:
            raise StorageError('Invalid storage key')
        normalized=key.replace('\\\\','/')
        if normalized.startswith('/') or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._/-]*',normalized):
            raise StorageError('Invalid storage key')
        parts=normalized.split('/')
        if any(part in ('','.','..') for part in parts):
            raise StorageError('Invalid storage key')
        path=self.root.joinpath(*parts).resolve()  # lgtm[py/path-injection]
        if path != self.root and self.root not in path.parents:
            raise StorageError('Invalid storage key')
        return path
    def put_bytes(self, key: str, data: bytes):
        path = self._path(key); path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(data)
    def get_bytes(self, key: str) -> bytes:
        path = self._path(key)
        if not path.is_file(): raise FileNotFoundError(key)
        return path.read_bytes()
    def exists(self, key: str) -> bool: return self._path(key).is_file()
    def delete(self, key: str):
        path=self._path(key)
        if path.exists(): path.unlink()
    def list_keys(self, prefix: str=''):
        base=self._path(prefix) if prefix else self.root
        if base.is_file(): return [prefix]
        if not base.exists(): return []
        return [p.relative_to(self.root).as_posix() for p in base.rglob('*') if p.is_file()]
    def delete_prefix(self, prefix: str=''):
        for key in self.list_keys(prefix): self.delete(key)
    def health(self):
        probe='.healthcheck'; self.put_bytes(probe,b'ok'); ok=self.get_bytes(probe)==b'ok'; self.delete(probe); return ok

class AzureBlobStorage:
    backend='azure'
    def __init__(self, connection_string: str, container: str, account_url: str=''):
        try:
            from azure.storage.blob import BlobServiceClient
        except ImportError as exc:
            raise StorageError('azure-storage-blob is required for Azure storage') from exc
        if account_url:
            try:
                from azure.identity import DefaultAzureCredential
            except ImportError as exc:
                raise StorageError('azure-identity is required for passwordless Azure storage') from exc
            svc=BlobServiceClient(account_url=account_url,credential=DefaultAzureCredential())
            self.auth='managed_identity'
        elif connection_string:
            svc=BlobServiceClient.from_connection_string(connection_string)
            self.auth='connection_string'
        else:
            raise StorageError('Set SALUS_AZURE_STORAGE_ACCOUNT_URL for managed identity or SALUS_AZURE_STORAGE_CONNECTION_STRING')
        self.container=svc.get_container_client(container)
        try: self.container.create_container()
        except Exception: pass
    def put_bytes(self,key,data): self.container.upload_blob(name=key,data=data,overwrite=True)
    def get_bytes(self,key): return self.container.download_blob(key).readall()
    def exists(self,key): return self.container.get_blob_client(key).exists()
    def delete(self,key):
        try: self.container.delete_blob(key)
        except Exception: pass
    def list_keys(self,prefix=''): return [b.name for b in self.container.list_blobs(name_starts_with=prefix)]
    def delete_prefix(self,prefix=''):
        for key in self.list_keys(prefix): self.delete(key)
    def health(self):
        probe='.healthcheck'; self.put_bytes(probe,b'ok'); ok=self.get_bytes(probe)==b'ok'; self.delete(probe); return ok

def build_storage(base_dir: str):
    backend=os.getenv('SALUS_STORAGE_BACKEND','local').strip().lower()
    if backend=='azure':
        return AzureBlobStorage(
            secret('SALUS_AZURE_STORAGE_CONNECTION_STRING',''),
            os.getenv('SALUS_AZURE_STORAGE_CONTAINER','salus-thira-evidence'),
            os.getenv('SALUS_AZURE_STORAGE_ACCOUNT_URL','').strip(),
        )
    root=os.getenv('SALUS_LOCAL_STORAGE_DIR',os.path.join(base_dir,'attachments'))
    return LocalStorage(root)
