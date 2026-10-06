"""Execute the Jupyter document factory and file loader in a DOM test environment."""

import os
from pathlib import Path
import shutil
import subprocess

SOURCE = Path(__file__).resolve().parents[1]


def copied_integration(root):
    (root / "src").mkdir(parents=True)
    shutil.copy(SOURCE / "src/index.ts", root / "src/index.ts")


def test_default_factory_and_context_menu_open_encoded_local_files(tmp_path):
    copied_integration(tmp_path)
    script = r'''
const fs = require('fs');
const vm = require('vm');
const assert = require('assert/strict');
const ts = require('typescript');
const { JSDOM } = require('jsdom');
const { Signal } = require('@lumino/signaling');
(async () => {
const source = ts.transpileModule(fs.readFileSync(process.argv[1], 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2018 }
}).outputText;
for (const base of ['/', '/user/alice/', 'https://mgh.neurodesk.org/user/stebo85/']) {
  const dom = new JSDOM('<!doctype html><html><body></body></html>', {url: 'https://mgh.neurodesk.org'});
  const opened = [], types = [], factories = [], menus = [], downloads = [], requests = [];
  const blobs = new Map();
  let nextBlob = 0;
  const browserURL = class extends URL {};
  browserURL.createObjectURL = blob => { const url = `blob:https://mgh.neurodesk.org/${++nextBlob}`; blobs.set(url, blob); return url; };
  browserURL.revokeObjectURL = url => blobs.delete(url);
  const settings = { baseUrl: base, token: 'private-parent-token' };
  const goodResponse = () => ({ok: true, status: 200, headers: {get: () => 'application/octet-stream'}, blob: async () => new Blob(['volume bytes'])});
  let responseFor = async () => goodResponse();
  const services = { serverSettings: settings, contents: {
    getDownloadUrl: async path => { downloads.push(path); return `https://mgh.neurodesk.org/download/${encodeURIComponent(path)}?_xsrf=session-xsrf`; }
  }};
  const settle = async () => { for (let i=0; i<10; i++) await new Promise(resolve => setImmediate(resolve)); };
  let selected;
  const commands = new Map();
  class Widget {
    constructor() { this.node = dom.window.document.createElement('div'); this.isDisposed = false; }
    dispose() { this.isDisposed = true; }
  }
  class Factory { constructor(options) { this.options = options; } }
  class DocumentWidget { constructor(options) { Object.assign(this, options); } close() {} }
  const modules = {
    '@jupyterlab/application': {},
    '@jupyterlab/docregistry': { ABCWidgetFactory: Factory, DocumentWidget },
    '@jupyterlab/filebrowser': { IFileBrowserFactory: Symbol() },
    '@jupyterlab/coreutils': { PageConfig: { getBaseUrl: () => base } },
    '@lumino/widgets': { Widget },
    '@jupyterlab/services': { ServerConnection: { makeRequest: async (url, init, supplied) => {
      assert.equal(supplied, settings); assert.equal(init.method, 'GET');
      requests.push(url);
      return responseFor(url, init);
    } }}
  };
  const sandbox = { exports: {}, require: name => modules[name], console,
    document: dom.window.document, URL: browserURL, AbortController,
    window: { open: () => { throw Error('Unexpected external browser tab'); } },
    setTimeout: () => { throw Error('Unexpected auto-close'); } };
  vm.runInNewContext(source, sandbox);
  sandbox.exports.default.activate({
    serviceManager: services,
    commands: { addCommand: (id, command) => commands.set(id, command),
      execute: (id, args) => { assert.equal(id, 'docmanager:open'); opened.push(args); } },
    contextMenu: { addItem: item => menus.push(item) },
    docRegistry: { addFileType: type => types.push(type), addWidgetFactory: f => factories.push(f) }
  }, { tracker: { currentWidget: { selectedItems: function* () { if (selected) yield selected; } } } });
  assert.deepEqual(Array.from(factories[0].options.defaultFor), ['nifti', 'nifti-gz', 'nvd']);
  assert.equal(factories[0].options.name, 'FreeBrowse');
  assert.equal(menus[0].command, 'freebrowse:open');
  const command = commands.get('freebrowse:open');
  for (const name of ['brain.nii', 'brain.nii.gz', 'scene.nvd', 'Bräin # & ? 100%.NII.GZ', 'scene # &.NVD']) {
    const path = `data folder/${name}`;
    selected = { name, path };
    assert.equal(command.isVisible(), true);
    command.execute();
    const request = opened.pop();
    assert.equal(request.path, path);
    assert.equal(request.factory, 'FreeBrowse');
    const context = { path };
    context.pathChanged = new Signal(context);
    const widget = factories[0].createNewWidget(context);
    await settle();
    assert.equal(downloads.at(-1), path, 'Use the Jupyter contents service to resolve the file');
    assert.equal(requests.at(-1), `https://mgh.neurodesk.org/download/${encodeURIComponent(path)}?_xsrf=session-xsrf`);
    const frame = widget.content.node.querySelector('iframe');
    assert.equal(frame.title, 'FreeBrowse');
    for (const value of [frame.src]) {
      const url = new URL(value, 'https://hub.example');
      assert.equal(url.pathname, new URL(`${base}freebrowse/`, 'https://hub.example').pathname);
      assert.equal(url.hash, '');
      const parameter = name.toLowerCase().endsWith('.nvd') ? 'nvd' : 'vol';
      assert.equal(Array.from(url.searchParams).length, 2);
      assert.equal(url.searchParams.get('filename'), name);
      const file = url.searchParams.get(parameter);
      assert.ok(blobs.has(file), 'The viewer receives locally fetched bytes');
      assert.equal(url.href.includes(settings.token), false);
      assert.equal(url.href.includes('session-xsrf'), false);
    }
    const secondContext = { path: 'another.nii' };
    secondContext.pathChanged = new Signal(secondContext);
    const second = factories[0].createNewWidget(secondContext);
    await settle();
    const originalBlob = new URL(frame.src).searchParams.get(name.toLowerCase().endsWith('.nvd') ? 'nvd' : 'vol');
    context.path = 'renamed #.nii.gz';
    context.pathChanged.emit(context.path);
    await settle();
    assert.equal(new URL(frame.src).searchParams.get('filename'), 'renamed #.nii.gz');
    assert.equal(blobs.has(originalBlob), false);
    assert.equal(new URL(second.content.node.querySelector('iframe').src).searchParams.get('filename'), 'another.nii');
    widget.content.dispose();
    assert.equal(frame.src, 'about:blank');
    context.path = 'after-close.nii';
    context.pathChanged.emit(context.path);
    await settle();
    assert.equal(frame.src, 'about:blank');
    second.content.dispose();
    assert.equal(blobs.size, 0);
  }
  for (const response of [{ok: false, status: 403}, {ok: true, status: 200}]) {
    responseFor = async () => ({...response, headers: {get: () => 'text/html'}});
    const failedContext = {path: 'denied.nii'};
    failedContext.pathChanged = new Signal(failedContext);
    const failed = factories[0].createNewWidget(failedContext);
    await settle();
    assert.equal(failed.content.node.textContent, 'FreeBrowse could not load this file through Jupyter.');
    assert.equal(failed.content.node.querySelector('iframe'), null);
    failed.content.dispose();
  }
  let finishOld;
  responseFor = async () => ({...goodResponse(), blob: () => new Promise(resolve => { finishOld = resolve; })});
  const pendingContext = {path: 'old.nii'};
  pendingContext.pathChanged = new Signal(pendingContext);
  const pending = factories[0].createNewWidget(pendingContext);
  await settle();
  responseFor = async () => goodResponse();
  pendingContext.path = 'new.nii';
  pendingContext.pathChanged.emit(pendingContext.path);
  await settle();
  const liveFrame = pending.content.node.querySelector('iframe');
  const latest = liveFrame.src;
  finishOld(new Blob(['stale bytes']));
  await settle();
  assert.equal(liveFrame.src, latest, 'A stale download cannot replace the renamed file');
  assert.equal(new URL(latest).searchParams.get('filename'), 'new.nii');
  pending.content.dispose();
  responseFor = async () => ({...goodResponse(), blob: () => new Promise(resolve => { finishOld = resolve; })});
  const closedContext = {path: 'closed.nii'};
  closedContext.pathChanged = new Signal(closedContext);
  const closed = factories[0].createNewWidget(closedContext);
  await settle();
  closed.content.dispose();
  finishOld(new Blob(['discarded bytes']));
  await settle();
  assert.equal(blobs.size, 0, 'A download completing after close must not retain a blob');
  selected = { name: 'notes.txt', path: 'notes.txt' };
  assert.equal(command.isVisible(), false);
  selected = undefined;
  assert.equal(command.isVisible(), false);
}
})().catch(error => { console.error(error); process.exitCode = 1; });
'''
    environment = dict(os.environ)
    environment["NODE_PATH"] = os.environ.get(
        "NEURODESKTOP_LAUNCHER_TEST_NODE_MODULES",
        "/tmp/neurodesk-launcher-tests/node_modules",
    )
    result = subprocess.run(
        ["node", "-e", script, str(tmp_path / "src/index.ts")],
        env=environment, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_frontend_preserves_filename_when_loading_a_blob(tmp_path):
    copied_integration(tmp_path)
    frontend = tmp_path / "frontend"
    loader = frontend / "src/hooks/use-file-loading.ts"
    loader.parent.mkdir(parents=True)
    shutil.copy(SOURCE.parent / "frontend/src/hooks/use-file-loading.ts", loader)
    script = r'''
const fs = require('fs'), vm = require('vm'), assert = require('assert/strict');
const ts = require('typescript');
const source = ts.transpileModule(fs.readFileSync(process.argv[1], 'utf8').replace('import.meta.env.VITE_SERVERLESS', '"true"'), {
  compilerOptions: {module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2018}
}).outputText;
(async () => {
  for (const filename of ['tof_sub004.nii', 'brain # & ü.nii.gz', undefined]) {
    const effects = [], volumes = [];
    const noop = () => {};
    const state = {showUploader: true, setShowUploader: noop, setCurrentImageIndex: noop,
      incrementVolumeVersion: noop, setCurrentSurfaceIndex: noop, setActiveTab: noop};
    const query = new URLSearchParams({vol: filename ? 'blob:https://mgh.neurodesk.org/local-bytes' : 'https://example.org/legacy.nii'});
    if (filename) query.set('filename', filename);
    const modules = {
      react: {useCallback: f => f, useRef: value => ({current: value}), useEffect: f => effects.push(f)},
      '@/store': {useFreeBrowseStore: selector => selector(state)},
      '@niivue/niivue': {}
    };
    const sandbox = {exports: {}, require: name => modules[name], console, URLSearchParams,
      window: {location: {search: '?' + query}, addEventListener: noop, removeEventListener: noop}};
    vm.runInNewContext(source, sandbox);
    sandbox.exports.useFileLoading({current: {canvas: {}, opts: {}, volumes: [], addVolumeFromUrl: async volume => volumes.push(volume)}}, noop, noop, noop, noop, noop);
    effects.forEach(effect => effect());
    for (let i=0; i<10; i++) await new Promise(resolve => setImmediate(resolve));
    assert.equal(volumes.length, 1);
    assert.equal(volumes[0].name, filename || 'legacy.nii');
    assert.equal(volumes[0].url, query.get('vol'));
  }
})().catch(error => {console.error(error); process.exitCode=1;});
'''
    environment = dict(os.environ, NODE_PATH=os.environ.get(
        "NEURODESKTOP_LAUNCHER_TEST_NODE_MODULES", "/tmp/neurodesk-launcher-tests/node_modules"))
    result = subprocess.run(["node", "-e", script, str(loader)],
                            env=environment, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


