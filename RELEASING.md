# Publicação

O AutoDiag publica no PyPI pelo workflow `.github/workflows/release.yml`,
que só executa quando uma GitHub Release é publicada. A autenticação atual é
por **token de API** (secret `PYPI_API_TOKEN` em Settings → Secrets and
variables → Actions).

> Trusted Publishing (OIDC) é preferível por dispensar segredo de longa
> duração; o passo a passo para voltar a ele está comentado no próprio
> `release.yml` (remover o bloco `with:` e devolver `permissions:
> id-token: write`, após cadastrar o publisher em pypi.org com
> Owner `lucianoon`, Repository `autodiag`, Workflow `release.yml`,
> Environment `pypi`).

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
