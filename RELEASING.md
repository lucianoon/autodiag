# Publicação

O AutoDiag publica no PyPI por Trusted Publishing (OIDC). Não use token PyPI
de longa duração no GitHub.

## Configuração única no PyPI

No projeto `autodiag`, em **Manage → Publishing**, adicione um publisher:

| Campo | Valor |
|---|---|
| Owner | `lucianoon` |
| Repository | `autodiag` |
| Workflow | `release.yml` |
| Environment | `pypi` |

O workflow fica em `.github/workflows/release.yml` e só executa quando uma
GitHub Release é publicada.

## Checklist de versão

1. Atualize a versão em `pyproject.toml` e `uv.lock`.
2. Mova as mudanças de `Não publicado` para a nova versão em `CHANGELOG.md`.
3. Execute `uv lock --check`, lint, mypy, testes e `uv build`.
4. Faça merge em `main` e aguarde CI e CodeQL.
5. Crie uma GitHub Release com tag `vX.Y.Z` apontando para `main`.
6. Acompanhe o workflow **Release**; ele exige que a tag corresponda exatamente
   à versão do pacote antes de publicar wheel e sdist no PyPI.

Versões do PyPI e tags publicadas são imutáveis. Se o workflow falhar antes do
upload, corrija o problema sem reutilizar uma versão que já tenha chegado ao
PyPI.
