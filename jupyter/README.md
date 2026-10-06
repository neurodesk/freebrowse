# Jupyter integration

The JupyterLab document factory embeds FreeBrowse in a document tab. It resolves
local downloads through Jupyter Contents and fetches them with ServerConnection,
then passes a temporary blob URL and the original filename to the viewer.
Renames cancel pending downloads; closing a tab unloads the iframe and revokes
its blob URL. NIfTI and NiiVue documents support encoded filenames and JupyterHub
base paths without placing server credentials in viewer URLs.

The packaged static assets require Jupyter authentication. Same-origin GET and
HEAD requests are exempt from the additional XSRF token requirement on this
static directory only. This allows browser module scripts and crossorigin
stylesheets to authenticate using their session cookie on JupyterHub. Fetch
Metadata must identify the request as same-origin; cross-site requests, requests
without that metadata, and mutations retain the normal XSRF checks. The handler
never serves workspace files or API responses.

Build the frontend with `npm run build:jupyter` in `frontend/`, then build and
install the federated extension from this directory with `jlpm build:prod` and
`pip install .`.

Run the authentication regressions with:

```sh
python -m pip install pytest jupyter-server 'jupyterhub==6.0.1'
PYTHONPATH=jupyter python -m pytest jupyter/tests/test_handlers.py
```

The tests execute JupyterHub's signed-cookie and XSRF code over real HTTP.
Only the Hub API token lookup is replaced with a local fixture. They cover
root and user base paths, module and stylesheet requests, anonymous and invalid
cookies, cross-site requests, missing metadata, mutations, and path traversal.

Forks run the Jupyter and frontend validation workflow with a read-only token.
The inherited GitHub Pages build, deployment, and release jobs run only in
`freesurfer/freebrowse`. Forks do not configure Pages, request a deployment token,
or create upstream version tags/releases, including on manual dispatch.
