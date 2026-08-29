import os
from pathlib import Path

class StorageError(RuntimeError):
    pass

class LocalStorage:
    def __init__(self, root: str):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
    def _path(self, key: str) -> Path:
        safe = key.replace('\\','/').lstrip('/')
        path = (self.root / safe).resolve()
        if self.root.resolve() not in path.parents and path != self.root.resolve():
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
    def __init__(self, connection_string: str, container: str):
        if not connection_string: raise StorageError('SALUS_AZURE_STORAGE_CONNECTION_STRING is required')
        try:
            from azure.storage.blob import BlobServiceClient
        except ImportError as exc:
            raise StorageError('azure-storage-blob is required for Azure storage') from exc
        svc=BlobServiceClient.from_connection_string(connection_string)
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
        return AzureBlobStorage(os.getenv('SALUS_AZURE_STORAGE_CONNECTION_STRING',''),os.getenv('SALUS_AZURE_STORAGE_CONTAINER','salus-thira-evidence'))
    root=os.getenv('SALUS_LOCAL_STORAGE_DIR',os.path.join(base_dir,'attachments'))
    return LocalStorage(root)
