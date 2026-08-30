import os
from dataclasses import dataclass

class SecretProviderError(RuntimeError):
    pass

@dataclass
class SecretStatus:
    backend: str
    configured: bool
    detail: str

class EnvironmentSecretProvider:
    backend='env'
    def get(self, name: str, default: str='') -> str:
        return os.getenv(name, default)
    def health(self) -> SecretStatus:
        return SecretStatus(self.backend, True, 'Operating-system environment variables')

class AzureKeyVaultSecretProvider:
    backend='azure_keyvault'
    def __init__(self, vault_url: str):
        if not vault_url:
            raise SecretProviderError('SALUS_KEY_VAULT_URL is required for Azure Key Vault')
        try:
            from azure.identity import DefaultAzureCredential
            from azure.keyvault.secrets import SecretClient
        except ImportError as exc:
            raise SecretProviderError('azure-identity and azure-keyvault-secrets are required for Azure Key Vault') from exc
        self.vault_url=vault_url.rstrip('/')
        self.credential=DefaultAzureCredential()
        self.client=SecretClient(vault_url=self.vault_url, credential=self.credential)
    def get(self, name: str, default: str='') -> str:
        direct=os.getenv(name)
        if direct is not None:
            return direct
        secret_name=os.getenv(f'{name}_KEYVAULT_NAME') or name.lower().replace('_','-')
        try:
            value=self.client.get_secret(secret_name).value
            return value if value is not None else default
        except Exception as exc:
            if default != '':
                return default
            raise SecretProviderError('Unable to retrieve managed secret') from exc
    def health(self) -> SecretStatus:
        try:
            self.credential.get_token('https://vault.azure.net/.default')
            return SecretStatus(self.backend, True, 'Key Vault identity available')
        except Exception:
            return SecretStatus(self.backend, False, 'Key Vault credential unavailable')


def build_secret_provider():
    backend=os.getenv('SALUS_SECRET_BACKEND','env').strip().lower()
    if backend in ('azure','azure_keyvault','keyvault'):
        return AzureKeyVaultSecretProvider(os.getenv('SALUS_KEY_VAULT_URL','').strip())
    return EnvironmentSecretProvider()

_PROVIDER=None

def provider():
    global _PROVIDER
    if _PROVIDER is None:
        _PROVIDER=build_secret_provider()
    return _PROVIDER


def secret(name: str, default: str='') -> str:
    return provider().get(name, default)


def readiness():
    try:
        s=provider().health()
        return {'backend':s.backend,'configured':s.configured,'detail':s.detail}
    except Exception:
        return {'backend':os.getenv('SALUS_SECRET_BACKEND','env'),'configured':False,'detail':'Secret provider unavailable'}
